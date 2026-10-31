using Wordslab.Wizard.Core;
using Wordslab.Wizard.Core.Scripts;
using Xunit;

namespace Wizard.Tests;

/// <summary>A scriptable fake process: each command maps to (exit code, stdout lines, stderr lines).</summary>
sealed class FakeProcess : ICommandExecutor
{
    private readonly Dictionary<string, (int exit, string[] stdout, string[] stderr)> _table;
    public List<(string command, string[] args)> Calls { get; } = new();

    public FakeProcess(Dictionary<string, (int, string[], string[])> table) => _table = table;

    public Task<int> RunAsync(Command command, Action<ReportLine> report, CancellationToken cancel = default)
    {
        Calls.Add((command.Program, command.Args.ToArray()));
        if (!_table.TryGetValue(command.Program, out var entry))
            return Task.FromResult(127); // command not found
        foreach (var l in entry.stdout) report(new ReportLine(ReportKind.Stdout, l));
        foreach (var l in entry.stderr) report(new ReportLine(ReportKind.Stderr, l));
        return Task.FromResult(entry.exit);
    }
}

/// <summary>A fake whose responses depend on the argv — for `wsl.exe` called repeatedly with
/// different paths (wslpath translation of two different files).</summary>
sealed class ArgAwareProcess : ICommandExecutor
{
    private readonly Func<Command, (int exit, string[] stdout)> _respond;
    public List<Command> Calls { get; } = new();

    public ArgAwareProcess(Func<Command, (int, string[])> respond) => _respond = respond;

    public Task<int> RunAsync(Command command, Action<ReportLine> report, CancellationToken cancel = default)
    {
        Calls.Add(command);
        var (exit, stdout) = _respond(command);
        foreach (var l in stdout) report(new ReportLine(ReportKind.Stdout, l));
        return Task.FromResult(exit);
    }

    public static ArgAwareProcess WslWithTranslatedPaths() => new(c =>
        c.Args.Count > 4 && c.Args[2] == "wslpath"
            ? (0, new[] { c.Args[4][0] == '/'
                ? "/mnt/c" + c.Args[4]                                        // /repo/x -> /mnt/c/repo/x
                : "/mnt/c/" + c.Args[4][2..].TrimStart('\\').Replace('\\', '/') }) // C:\x\y -> /mnt/c/x/y
            : (0, Array.Empty<string>()));
}

static class Contexts
{
    public static InstallContext Make(ICommandExecutor executor, string installerDir = "/repo/installer") => new()
    {
        InstallerDir = installerDir,
        // The real v1 parameters the wizard writes (#87 contract): program folder + one
        // volume_<DRIVE> key per enabled drive.
        Parameters = new Dictionary<string, string>
        {
            ["install_dir"] = @"C:\wordslab-platform",
            ["volume_C"] = @"C:\wordslab-platform",
            ["volume_D"] = @"D:\wordslab-platform",
        },
        ParametersFile = "/tmp/wordslab-install-parameters.json",
        WslPaths = new WslPathTranslator(executor),
    };
}

public class ScriptPlanTests
{
    [Fact]
    public async Task Windows_specific_steps_run_on_the_host_or_via_wsl()
    {
        var proc = ArgAwareProcess.WslWithTranslatedPaths();
        var ctx = Contexts.Make(proc);

        var s1 = await new Script01NetworkReachability().PlanAsync(ctx);
        string host = Path.GetFileNameWithoutExtension(s1.Single().Program);
        Assert.Contains(host, new[] { "pwsh", "powershell" });

        var s3 = await new Script03UvPythonInDistro().PlanAsync(ctx);
        Assert.Equal(Wsl.Exe, s3.Single().Program);
        Assert.Equal(new[] { "-d", "wordslab-platform-vm", "--", "bash" }, s3.Single().Args.Take(4));
        Assert.EndsWith("scripts/windows/03-engine.sh", s3.Single().Args[4]);
    }

    // ---- #88: every step's real command plan, pinned as argv ----

    [Fact]
    public async Task Step1_checks_reachability_of_github_AND_pypi_and_fails_loudly()
    {
        var ctx = Contexts.Make(ArgAwareProcess.WslWithTranslatedPaths());
        var cmd = (await new Script01NetworkReachability().PlanAsync(ctx)).Single();

        Assert.Equal(new[] { "-NoProfile", "-Command" }, cmd.Args.Take(2));
        string body = cmd.Args[2];
        Assert.Contains("https://github.com", body);
        Assert.Contains("https://pypi.org", body);
        Assert.Contains("-Method Head", body);          // probes, not just resolves DNS
        Assert.Contains("exit 1", body);                // unreachable -> loud non-zero exit
        Assert.Contains("Internet connection OK", body); // its own final human sentence
        Assert.DoesNotContain("placeholder", body);
    }

    [Fact]
    public async Task Step2_switches_the_feature_on_then_imports_the_named_wordslab_vm()
    {
        var ctx = Contexts.Make(ArgAwareProcess.WslWithTranslatedPaths());
        var cmds = await new Script02WslFeatureAndVm().PlanAsync(ctx);

        Assert.Equal(2, cmds.Count);
        Assert.All(cmds, c => Assert.Equal(new[] { "-NoProfile", "-Command" }, c.Args.Take(2)));
        string feature = cmds[0].Args[2];
        Assert.Contains("wsl --status", feature);
        Assert.Contains("wsl --install --no-distribution", feature);
        // The documented exit that lets the window ask Windows for admin ONCE (one UAC) — and
        // nothing else. A generic failure must not trigger the elevation dance.
        Assert.Contains("exit 3", feature);
        Assert.DoesNotContain("Restart the computer, then open Wordslab", feature);
        string vm = cmds[1].Args[2];
        // The #88 ruling: wsl --import (never wsl --install distro, never wsl --mount) — the disk
        // lands in a plain folder under the program folder WSL itself manages.
        Assert.Contains("wsl --import wordslab-platform-vm", vm);
        Assert.Contains(Script02WslFeatureAndVm.UbuntuRootfsUrl, vm);
        Assert.Contains(Path.Combine(@"C:\wordslab-platform", "wordslab-platform-vm"), vm); // host-native separator
        Assert.Contains("systemd = true", vm);
        Assert.Contains("appendWindowsPath = false", vm);   // no interop: the VM never calls Windows
        Assert.Contains("wsl --shutdown", vm);              // applies wsl.conf visibly
        Assert.DoesNotContain("placeholder", feature + vm);
    }

    [Fact]
    public async Task Step3_runs_the_engine_script_FILE_never_an_inline_bash_c_body()
    {
        // Live bug (2026-10-31): a 785-byte multi-line body with embedded quotes, passed as
        // `wsl -- bash -c <body>`, is re-split on the Linux side -> bash sees an unterminated
        // quote -> exit 2. The body is a script FILE now: exactly one translated path.
        var proc = ArgAwareProcess.WslWithTranslatedPaths();
        var ctx = Contexts.Make(proc);
        var cmd = (await new Script03UvPythonInDistro().PlanAsync(ctx)).Single();

        Assert.Equal(new[] { "-d", "wordslab-platform-vm", "--", "bash",
                             "/mnt/c/repo/installer/scripts/windows/03-engine.sh",
                             "--parameters", "/mnt/c/tmp/wordslab-install-parameters.json" },
                     cmd.Args);
        Assert.DoesNotContain("-c", cmd.Args);              // no inline body survives
        Assert.Equal(System.Text.Encoding.UTF8, cmd.OutputEncoding);
    }

    [Fact]
    public async Task Step4_creates_one_linux_disk_instance_per_enabled_volume_then_runs_the_shared_script()
    {
        var proc = ArgAwareProcess.WslWithTranslatedPaths();
        var ctx = Contexts.Make(proc);
        var cmds = await new Script04DataVolumes().PlanAsync(ctx);

        // C: and D: each get their own guarded import command; the shared script runs last.
        Assert.Equal(3, cmds.Count);
        string diskC = cmds[0].Args[2];
        Assert.Contains("wsl --import wordslab-platform-diskc", diskC);
        // Path.Combine is host-native: backslashes on Windows where this runs, slashes if a Linux
        // box runs the tests - pin the formula, not one separator.
        Assert.Contains(Path.Combine(@"C:\wordslab-platform", "wordslab-platform-diskc"), diskC);
        Assert.Contains(Script04DataVolumes.AlpineRootfsUrl, diskC);
        string diskD = cmds[1].Args[2];
        Assert.Contains("wsl --import wordslab-platform-diskd", diskD);
        Assert.Contains(Path.Combine(@"D:\wordslab-platform", "wordslab-platform-diskd"), diskD);
        // The disk instance publishes /volume into the shared /mnt/wsl (notebooks mechanism), and
        // the instance is terminated after wsl.conf so the config actually applies at next start:
        Assert.Contains("mount --bind /volume /mnt/wsl/wordslab-platform-diskd", diskD);
        Assert.Contains("wsl --terminate wordslab-platform-diskd", diskD);
        var shared = cmds[2];
        Assert.Equal(new[] { "-d", "wordslab-platform-vm", "--", "bash",
                             "/mnt/c/repo/installer/scripts/distro/04-data-volumes.sh",
                             "--parameters", "/mnt/c/tmp/wordslab-install-parameters.json" }, shared.Args);
    }

    [Fact]
    public async Task Step6_appends_the_front_door_probe_after_the_shared_script()
    {
        var proc = ArgAwareProcess.WslWithTranslatedPaths();
        var ctx = Contexts.Make(proc);
        var cmds = await new Script06FrontDoor().PlanAsync(ctx);

        Assert.Equal(2, cmds.Count);
        Assert.Equal(new[] { "-d", "wordslab-platform-vm", "--", "bash" }, cmds[0].Args.Take(4));
        string probe = cmds[1].Args[2];
        Assert.Contains($"-d {Wsl.VmDistro} -- hostname -I", probe);
        Assert.Contains("wordslab-front-door.url", probe);   // the handoff address the window reads
        Assert.Contains("one port, one certificate", probe); // its own final human sentence
    }

    [Fact]
    public async Task Distro_shell_steps_translate_script_AND_parameters_then_run_bash()
    {
        var proc = ArgAwareProcess.WslWithTranslatedPaths();
        var ctx = Contexts.Make(proc);

        var commands = await new Script04DataVolumes().PlanAsync(ctx);

        // Planning runs two visible translations: the script file and the parameters file.
        Assert.Equal(2, proc.Calls.Count);
        Assert.Equal(new[] { "wslpath", "-u" }, proc.Calls[0].Args.Skip(2).Take(2));
        Assert.Equal(new[] { "wslpath", "-u" }, proc.Calls[1].Args.Skip(2).Take(2));
        // The shared script file reads the same parameters contract the UI wrote (#88): the
        // parameters file crosses the boundary translated, exactly like the script path. Step 4
        // prepends its disk commands, so the shared script is the LAST command of the plan.
        Assert.Equal(new[] { "-d", "wordslab-platform-vm", "--", "bash",
                             "/mnt/c/repo/installer/scripts/distro/04-data-volumes.sh",
                             "--parameters", "/mnt/c/tmp/wordslab-install-parameters.json" },
                     commands.Last().Args);
    }

    [Fact]
    public async Task Distro_shell_steps_fall_back_to_the_raw_path_and_fail_visibly_without_wsl()
    {
        // No WSL at all: wslpath fails; the step must still run and fail loudly (wsl's own error),
        // never silently skip.
        var proc = new FakeProcess(new Dictionary<string, (int, string[], string[])>());
        var ctx = Contexts.Make(proc);

        var commands = await new Script04DataVolumes().PlanAsync(ctx);

        Assert.Equal(ctx.DistroScript("distro/04-data-volumes.sh"), commands.Last().Args[4]);
    }

    [Fact]
    public async Task Distro_python_steps_run_the_distro_python_on_translated_paths()
    {
        var proc = ArgAwareProcess.WslWithTranslatedPaths();
        var ctx = Contexts.Make(proc);

        var step = new TestStep();
        var commands = await step.PlanAsync(ctx);

        Assert.Equal(new[] { "-d", "wordslab-platform-vm", "--", "python3", "/mnt/c/repo/installer/python/steps/step99_demo.py" }, commands.Single().Args);
    }

    sealed class TestStep : DistroPythonScript
    {
        public override int Number => 99;
        public override string Title => "Demo python step (#88 shape)";
        protected override string PythonFile => "steps/step99_demo.py";
    }

    [Fact]
    public void The_windows_journey_is_six_numbered_scripts_without_gaps()
    {
        var journey = new NumberedScript[]
        {
            new Script01NetworkReachability(), new Script02WslFeatureAndVm(), new Script03UvPythonInDistro(),
            new Script04DataVolumes(), new Script05FirstPlatformCore(), new Script06FrontDoor(),
        };
        Assert.Equal(new[] { 1, 2, 3, 4, 5, 6 }, journey.Select(s => s.Number));
        Assert.All(journey, s => Assert.False(string.IsNullOrWhiteSpace(s.Title)));
    }
}

public class JourneyRunnerTests
{
    [Fact]
    public async Task Runs_scripts_in_order_and_streams_their_status_and_output()
    {
        var proc = new FakeProcess(new() { ["ok"] = (0, new[] { "hello" }, Array.Empty<string>()) });
        var reports = new List<Report>();
        var runner = new JourneyRunner(proc);
        var ctx = Contexts.Make(proc);
        var step = new SingleCommandScript(1, "First", "ok");

        var results = await runner.RunAsync(new[] { step }, ctx, reports.Add);

        Assert.True(results.Single().Success);
        Assert.Contains(reports, r => r is { Step: 1, Kind: ReportKind.Info } && r.Text == "First");
        Assert.Contains(reports, r => r.Kind == ReportKind.Start);   // the command status line
        Assert.Contains(reports, r => r is { Kind: ReportKind.Stdout } && r.Text == "hello");
        Assert.Contains(reports, r => r is { Kind: ReportKind.Success } && r.Text == "done");
    }

    [Fact]
    public async Task Stops_at_the_first_failure_loudly_and_skips_nothing_silently()
    {
        var proc = new FakeProcess(new()
        {
            ["fail"] = (7, Array.Empty<string>(), Array.Empty<string>()),
            ["never"] = (0, new[] { "should not run" }, Array.Empty<string>()),
        });
        var reports = new List<Report>();
        var runner = new JourneyRunner(proc);
        var ctx = Contexts.Make(proc);

        var results = await runner.RunAsync(
            new NumberedScript[] { new SingleCommandScript(1, "Fails", "fail"), new SingleCommandScript(2, "Never runs", "never") },
            ctx, reports.Add);

        Assert.Single(results);
        Assert.DoesNotContain("never", proc.Calls.Select(c => c.command));
        Assert.Contains(reports, r => r.Text.Contains("FAILED (exit 7)") && r.Text.Contains("nothing further is installed"));
    }

    [Fact]
    public async Task Python_probe_runs_python_INSIDE_the_named_wordslab_distro_not_wsl_version()
    {
        var proc = new FakeProcess(new() { [Wsl.Exe] = (0, new[] { "Python 3.12.4" }, Array.Empty<string>()) });
        Assert.True(await new JourneyRunner(proc).PythonAvailableInDistroAsync());
        // The regression this pins: `wsl.exe --version` would only prove WSL exists — and the live
        // Windows run proved the DEFAULT distro can lack the interpreter entirely ("bash: not found",
        // exit 127). Every distro-facing command must target the named Wordslab distro.
        Assert.Equal(new[] { "-d", "wordslab-platform-vm", "--", "python3", "--version" }, proc.Calls.Single().args);
    }

    sealed class SingleCommandScript(int number, string title, string program) : NumberedScript
    {
        public override int Number => number;
        public override string Title => title;
        public override Task<IReadOnlyList<Command>> PlanAsync(InstallContext ctx) =>
            Task.FromResult<IReadOnlyList<Command>>(new[] { new Command(program, Array.Empty<string>(), title) });
    }
}

public class ExecutorTests
{
    [Fact]
    public async Task Real_executor_streams_stdout_and_exit_code()
    {
        var lines = new List<ReportLine>();
        int exit = await new ProcessCommandExecutor()
            .RunAsync(new Command("sh", new[] { "-c", "echo one; echo two" }, "echo test"), lines.Add);

        Assert.Equal(0, exit);
        Assert.Equal(new[] { "one", "two" }, lines.Select(l => l.Text));
    }

    [Fact]
    public async Task Real_executor_mirrors_stderr_without_deadlocking_on_a_flooded_pipe()
    {
        // Regression: reading stdout to EOF first deadlocks when the process fills the stderr pipe.
        var lines = new List<ReportLine>();
        var task = new ProcessCommandExecutor().RunAsync(
            new Command("sh", new[] { "-c", "i=0; while [ $i -lt 4000 ]; do echo e$i >&2; i=$((i+1)); done; echo last" }, "flood"),
            lines.Add);

        // async timeout: the deadlock regression must not block a test thread (xUnit1031)
        var winner = await Task.WhenAny(task, Task.Delay(TimeSpan.FromSeconds(15)));
        Assert.True(winner == task, "ProcessCommandExecutor deadlocked");
        Assert.Equal(0, await task);
        Assert.Contains("last", lines.Select(l => l.Text));
        Assert.Equal(4000, lines.Count(l => l.Kind == ReportKind.Stderr));
    }
}

public class SupportTests
{
    [Fact]
    public void Disk_validation_accepts_drive_paths_and_rejects_junk()
    {
        Assert.Null(Parameters.ValidateDiskPath("D:\\"));
        Assert.Null(Parameters.ValidateDiskPath("/data")); // POSIX roots (Linux parity)
        Assert.NotNull(Parameters.ValidateDiskPath("not a path"));
        Assert.NotNull(Parameters.ValidateDiskPath("/")); // bare root is refused on purpose
    }

    [Fact]
    public void Windows_parameters_name_each_data_volume_after_its_drive()
    {
        var p = Parameters.ForWindows(@"C:\wordslab-platform",
            new[] { ("C:", @"C:\wordslab-platform"), ("d:", @"D:\wordslab-platform") });
        Assert.Equal(@"C:\wordslab-platform", p["install_dir"]);
        Assert.Equal(@"C:\wordslab-platform", p["volume_C"]);
        Assert.Equal(@"D:\wordslab-platform", p["volume_D"]); // drive letters normalize to upper case
        Assert.Equal(3, p.Count); // a disabled drive simply gets no key
    }

    [Fact]
    public void Volume_folders_must_sit_on_the_drive_they_name()
    {
        Assert.Null(Parameters.ValidateVolumeFolder(@"D:\wordslab-platform", "D:"));
        Assert.NotNull(Parameters.ValidateVolumeFolder(@"C:\wordslab-platform", "D:"));
        Assert.Null(Parameters.ValidateInstallDir(@"C:\wordslab-platform"));
        Assert.NotNull(Parameters.ValidateInstallDir("Wordslab"));
    }

    [Fact]
    public void Parameters_round_trip_as_json()
    {
        string path = Path.Combine(Path.GetTempPath(), $"wsparams-{Guid.NewGuid():N}.json");
        try
        {
            Parameters.Write(new Dictionary<string, string> { ["data_disk"] = "D:\\" }, path);
            var read = Parameters.Read(path);
            Assert.Equal("D:\\", read["data_disk"]);
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact]
    public async Task Wsl_path_translator_returns_the_trimmed_first_stdout_line()
    {
        var proc = new FakeProcess(new() { [Wsl.Exe] = (0, new[] { "  /mnt/c/data  " }, Array.Empty<string>()) });
        string? result = await new WslPathTranslator(proc).ToDistroPathAsync(@"C:\data");
        Assert.Equal("/mnt/c/data", result);
    }

    [Fact]
    public void Payload_locator_finds_the_repo_and_payload_layouts()
    {
        string repo = Path.Combine(Path.GetTempPath(), $"wsrepo-{Guid.NewGuid():N}");
        Directory.CreateDirectory(Path.Combine(repo, "installer", "python"));
        File.WriteAllText(Path.Combine(repo, "installer", "python", "tui.py"), "");
        Assert.Equal(Path.Combine(repo, "installer"), PayloadLocator.FindInstallerDir(Path.Combine(repo, "installer", "windows")));

        string payload = Path.Combine(Path.GetTempPath(), $"wspayload-{Guid.NewGuid():N}");
        Directory.CreateDirectory(Path.Combine(payload, "python"));
        File.WriteAllText(Path.Combine(payload, "python", "tui.py"), "");
        Assert.Equal(payload, PayloadLocator.FindInstallerDir(Path.Combine(payload, "deep", "deeper")));

        Assert.Null(PayloadLocator.FindInstallerDir(Path.GetPathRoot(Path.GetTempPath())!));
    }

    [Fact]
    public void PowerShellHost_prefers_pwsh_over_windows_powershell()
    {
        string tmp = Path.Combine(Path.GetTempPath(), "pshost-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tmp);
        string? saved = Environment.GetEnvironmentVariable("PATH");
        try
        {
            string pwsh = OperatingSystem.IsWindows() ? "pwsh.exe" : "pwsh";
            string wins = OperatingSystem.IsWindows() ? "powershell.exe" : "powershell";
            File.WriteAllText(Path.Combine(tmp, pwsh), "#!/bin/sh\nexit 0\n");
            File.WriteAllText(Path.Combine(tmp, wins), "#!/bin/sh\nexit 0\n");
            Environment.SetEnvironmentVariable("PATH", tmp);
            Assert.EndsWith(pwsh, PowerShellHost.Resolve());
        }
        finally
        {
            Environment.SetEnvironmentVariable("PATH", saved);
            Directory.Delete(tmp, recursive: true);
        }
    }

    [Fact]
    public void PowerShellHost_falls_back_to_windows_powershell_when_pwsh_is_absent()
    {
        string tmp = Path.Combine(Path.GetTempPath(), "psnone-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tmp);
        string? saved = Environment.GetEnvironmentVariable("PATH");
        try
        {
            Environment.SetEnvironmentVariable("PATH", tmp);
            string expected = OperatingSystem.IsWindows() ? "powershell.exe" : "pwsh";
            Assert.Equal(expected, PowerShellHost.Resolve());
        }
        finally
        {
            Environment.SetEnvironmentVariable("PATH", saved);
            Directory.Delete(tmp, recursive: true);
        }
    }

    [Fact]
    public async Task ProcessCommandExecutor_streams_stdout_with_no_window()
    {
        // Real process (no fake): the shared executor must capture output invisibly —
        // CreateNoWindow=true is what stops console apps flashing a window per command.
        var lines = new List<ReportLine>();
        var exe = OperatingSystem.IsWindows() ? "cmd.exe" : "/bin/echo";
        var args = OperatingSystem.IsWindows()
            ? new[] { "/c", "echo", "hello" }
            : new[] { "hello" };
        int exit = await new ProcessCommandExecutor()
            .RunAsync(new Command(exe, args, "say hello"), lines.Add);
        Assert.Equal(0, exit);
        Assert.Contains(lines, l => l.Kind == ReportKind.Stdout && l.Text.Trim() == "hello");
    }

    [Fact]
    public void wsl_commands_declare_their_utf8_output_encoding()
    {
        // ONE contract: UTF-8 everywhere. The executor sets WSL_UTF8=1 for wsl.exe, so its own
        // messages are UTF-8 too — matching the UTF-8 the Linux child's output already arrives
        // in. (Decoding that UTF-8 as UTF-16LE is the "lines of Chinese characters" bug.)
        Assert.Equal(System.Text.Encoding.UTF8, Wsl.PythonProbe().OutputEncoding);
        Assert.Equal(System.Text.Encoding.UTF8, Wsl.PathTranslate("C:\\x").OutputEncoding);
        Assert.Equal(System.Text.Encoding.UTF8, Wsl.RunBash("/x/y.sh").OutputEncoding);
        Assert.Equal(System.Text.Encoding.UTF8, Wsl.RunPython("/x/tui.py").OutputEncoding);
    }

    [Fact]
    public async Task no_command_body_carries_a_csharp_style_comment()
    {
        // #88 live bug: `exit 3 // = …` inside a PowerShell body — PowerShell reads // as
        // division and the bare '=' dies with ExpectedValueExpression at RUN time on Windows,
        // invisible to argv pinning. A leaked // (not part of a URL) is always this bug.
        var ctx = Contexts.Make(ArgAwareProcess.WslWithTranslatedPaths());
        var scripts = new NumberedScript[]
        {
            new Script01NetworkReachability(), new Script02WslFeatureAndVm(), new Script03UvPythonInDistro(),
            new Script04DataVolumes(), new Script05FirstPlatformCore(), new Script06FrontDoor(),
        };
        foreach (var script in scripts)
        foreach (var command in await script.PlanAsync(ctx))
        foreach (var arg in command.Args)
            Assert.DoesNotMatch(@"(?<!:)//", arg);
    }

    [Fact]
    public void the_path_layout_helpers_answer_the_ui_promise()
    {
        var volumes = InstallDirs.EnabledVolumes(new Dictionary<string, string>
        {
            ["install_dir"] = @"C:\wordslab-platform",
            ["volume_D"] = @"D:\wordslab-platform",
            ["volume_C"] = @"C:\wordslab-platform",
        });
        Assert.Equal(new[] { ("C:", @"C:\wordslab-platform"), ("D:", @"D:\wordslab-platform") }, volumes);

        Assert.Equal("wordslab-platform-diskd", InstallDirs.VolumeDistroName("d:"));
        Assert.Equal(Path.Combine(@"D:\wordslab-platform", "wordslab-platform-diskc"),
                     InstallDirs.VolumeDistroFolder(@"D:\wordslab-platform", "C:"));

        // A missing program folder is a broken internal state, named as one — never a silent default.
        Assert.Throws<InvalidOperationException>(() =>
            InstallDirs.ProgramFolderOrThrow(new Dictionary<string, string>()));
    }

    [Fact]
    public void front_door_address_reads_the_step6_file_and_falls_back_loudly_safely()
    {
        string dir = Path.Combine(Path.GetTempPath(), "wsfd-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(dir);
        try
        {
            string parametersFile = Path.Combine(dir, "wordslab-install-parameters.json");
            File.WriteAllText(parametersFile, "{}");
            Assert.Equal("https://wordslab.local/",
                FrontDoorAddress.ReadFor(parametersFile, "https://wordslab.local/")); // absent -> fallback

            File.WriteAllText(Path.Combine(dir, FrontDoorAddress.UrlFileName), "https://172.21.0.4/ \n");
            Assert.Equal("https://172.21.0.4/",
                FrontDoorAddress.ReadFor(parametersFile, "https://wordslab.local/"));

            File.WriteAllText(Path.Combine(dir, FrontDoorAddress.UrlFileName), "not-a-url");
            Assert.Equal("https://wordslab.local/",
                FrontDoorAddress.ReadFor(parametersFile, "https://wordslab.local/")); // junk -> fallback
        }
        finally
        {
            Directory.Delete(dir, recursive: true);
        }
    }

    [Fact]
    public void RunPython_keeps_duplicate_argv_entries()
    {
        var args = Wsl.RunPython("/t.py", new[] { "--flag", "--flag" }).Args;
        Assert.Equal(new[] { "-d", "wordslab-platform-vm", "--", "python3", "/t.py", "--flag", "--flag" }, args);
    }

    [Fact]
    public void every_wsl_command_targets_the_named_wordslab_distro()
    {
        // #88: the live Windows run died on the DEFAULT distro lacking bash. One distro name,
        // one place to change it (Wsl.VmDistro), every factory honors it.
        Assert.Equal("wordslab-platform-vm", Wsl.VmDistro);
        Assert.Equal(new[] { "-d", "wordslab-platform-vm" }, Wsl.PythonProbe().Args.Take(2));
        Assert.Equal(new[] { "-d", "wordslab-platform-vm" }, Wsl.PathTranslate("C:\\x").Args.Take(2));
        Assert.Equal(new[] { "-d", "wordslab-platform-vm" }, Wsl.RunBash("/x/y.sh").Args.Take(2));
        Assert.Equal(new[] { "-d", "wordslab-platform-vm" }, Wsl.RunPython("/x/t.py").Args.Take(2));
    }
}
