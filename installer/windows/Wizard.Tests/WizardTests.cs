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
        c.Args.Count > 0 && c.Args[0] == "wslpath"
            ? (0, new[] { c.Args[2][0] == '/'
                ? "/mnt/c" + c.Args[2]                                        // /repo/x -> /mnt/c/repo/x
                : "/mnt/c/" + c.Args[2][2..].TrimStart('\\').Replace('\\', '/') }) // C:\x\y -> /mnt/c/x/y
            : (0, Array.Empty<string>()));
}

static class Contexts
{
    public static InstallContext Make(ICommandExecutor executor, string installerDir = "/repo/installer") => new()
    {
        InstallerDir = installerDir,
        Parameters = new Dictionary<string, string> { ["data_disk"] = "D:\\" },
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
        Assert.Equal("pwsh", s1.Single().Program);

        var s3 = await new Script03UvPythonInDistro().PlanAsync(ctx);
        Assert.Equal(Wsl.Exe, s3.Single().Program);
        Assert.Equal(new[] { "--", "bash", "-c", "echo 'uv bootstrap: placeholder until #88'" }, s3.Single().Args);
    }

    [Fact]
    public async Task Distro_shell_steps_translate_the_path_then_run_bash()
    {
        var proc = ArgAwareProcess.WslWithTranslatedPaths();
        var ctx = Contexts.Make(proc);

        var commands = await new Script04DataVolumes().PlanAsync(ctx);

        Assert.Single(proc.Calls); // planning itself runs one visible command: the translation
        Assert.Equal(new[] { "wslpath", "-u" }, proc.Calls[0].Args.Take(2));
        Assert.Equal(new[] { "--", "bash", "/mnt/c/repo/installer/scripts/distro/04-data-volumes.sh" },
                     commands.Single().Args);
    }

    [Fact]
    public async Task Distro_shell_steps_fall_back_to_the_raw_path_and_fail_visibly_without_wsl()
    {
        // No WSL at all: wslpath fails; the step must still run and fail loudly (wsl's own error),
        // never silently skip.
        var proc = new FakeProcess(new Dictionary<string, (int, string[], string[])>());
        var ctx = Contexts.Make(proc);

        var commands = await new Script04DataVolumes().PlanAsync(ctx);

        Assert.Equal(ctx.DistroScript("distro/04-data-volumes.sh"), commands.Single().Args[2]);
    }

    [Fact]
    public async Task Distro_python_steps_run_the_distro_python_on_translated_paths()
    {
        var proc = ArgAwareProcess.WslWithTranslatedPaths();
        var ctx = Contexts.Make(proc);

        var step = new TestStep();
        var commands = await step.PlanAsync(ctx);

        Assert.Equal(new[] { "--", "python3", "/mnt/c/repo/installer/python/steps/step99_demo.py" }, commands.Single().Args);
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
            new Script01NetworkReachability(), new Script02WslDistroDisks(), new Script03UvPythonInDistro(),
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
    public async Task Python_probe_runs_python_INSIDE_the_distro_not_wsl_version()
    {
        var proc = new FakeProcess(new() { [Wsl.Exe] = (0, new[] { "Python 3.12.4" }, Array.Empty<string>()) });
        Assert.True(await new JourneyRunner(proc).PythonAvailableInDistroAsync());
        // The regression this pins: `wsl.exe --version` would only prove WSL exists.
        Assert.Equal(new[] { "--", "python3", "--version" }, proc.Calls.Single().args);
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
    public void Wsl_commands_declare_their_utf16le_output_encoding()
    {
        // wsl.exe (incl. wslpath) emits UTF-16LE; without the explicit encoding a real Windows
        // host decodes its output as NUL-corrupted text — the fakes cannot catch this drift.
        Assert.Equal(System.Text.Encoding.Unicode, Wsl.PythonProbe().OutputEncoding);
        Assert.Equal(System.Text.Encoding.Unicode, Wsl.PathTranslate("C:\\x").OutputEncoding);
        Assert.Equal(System.Text.Encoding.Unicode, Wsl.RunBash("/x/y.sh").OutputEncoding);
        Assert.Equal(System.Text.Encoding.Unicode, Wsl.RunPython("/x/tui.py").OutputEncoding);
    }

    [Fact]
    public void RunPython_keeps_duplicate_argv_entries()
    {
        var args = Wsl.RunPython("/t.py", new[] { "--flag", "--flag" }).Args;
        Assert.Equal(new[] { "--", "python3", "/t.py", "--flag", "--flag" }, args);
    }
}
