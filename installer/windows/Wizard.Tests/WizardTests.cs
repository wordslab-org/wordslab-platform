using Wordslab.Wizard;
using Wordslab.Wizard.Abstractions;
using Xunit;

namespace Wizard.Tests;

/// <summary>A scriptable fake process: each command maps to (exit code, stdout lines, stderr lines).</summary>
sealed class FakeProcess : IProcessRunner
{
    private readonly Dictionary<string, (int exit, string[] stdout, string[] stderr)> _table;
    public List<(string command, string[] args)> Calls { get; } = new();

    public FakeProcess(Dictionary<string, (int, string[], string[])> table) => _table = table;

    public int Run(string command, IReadOnlyList<string> args, Action<string>? onStdout, Action<string>? onStderr)
    {
        Calls.Add((command, args.ToArray()));
        if (!_table.TryGetValue(command, out var entry))
            return 127; // command not found
        foreach (var l in entry.stdout) onStdout?.Invoke(l);
        foreach (var l in entry.stderr) onStderr?.Invoke(l);
        return entry.exit;
    }
}

/// <summary>A fake whose responses depend on the argv, for commands called repeatedly
/// (e.g. `wsl.exe wslpath -u …` twice with different paths).</summary>
sealed class ArgAwareProcess : IProcessRunner
{
    private readonly Func<string, IReadOnlyList<string>, (int exit, string[] stdout)> _respond;
    public List<(string command, string[] args)> Calls { get; } = new();

    public ArgAwareProcess(Func<string, IReadOnlyList<string>, (int, string[])> respond) => _respond = respond;

    public int Run(string command, IReadOnlyList<string> args, Action<string>? onStdout, Action<string>? onStderr)
    {
        Calls.Add((command, args.ToArray()));
        var (exit, stdout) = _respond(command, args);
        foreach (var l in stdout) onStdout?.Invoke(l);
        return exit;
    }
}

public class ScriptRunnerTests
{
    private static (ScriptRunner runner, List<string> mirror, FakeProcess proc) Make(
        Dictionary<string, (int, string[], string[])> table)
    {
        var mirror = new List<string>();
        var proc = new FakeProcess(table);
        return (new ScriptRunner(proc, mirror.Add), mirror, proc);
    }

    [Fact]
    public void Runs_steps_in_order_and_mirrors_stdout_line_by_line()
    {
        var (runner, mirror, proc) = Make(new()
        {
            ["one"] = (0, new[] { "hello", "world" }, Array.Empty<string>()),
            ["two"] = (0, new[] { "done" }, Array.Empty<string>()),
        });
        var steps = new[]
        {
            new ScriptStep(1, "First", "one", Array.Empty<string>()),
            new ScriptStep(2, "Second", "two", Array.Empty<string>()),
        };

        var results = runner.RunAll(steps);

        Assert.Equal(2, results.Count);
        Assert.True(results.All(r => r.Success));
        Assert.Equal(new[] { "one", "two" }, proc.Calls.Select(c => c.command));
        Assert.Contains("[01] First", mirror);
        Assert.Contains("[01] hello", mirror);
        Assert.Contains("[01] world", mirror);
        Assert.Contains("[02] done", mirror);
    }

    [Fact]
    public void Mirrors_stderr_lines_loudly()
    {
        var (runner, mirror, _) = Make(new()
        {
            ["bad"] = (0, Array.Empty<string>(), new[] { "warning: careful" }),
        });
        runner.RunAll(new[] { new ScriptStep(3, "Warns", "bad", Array.Empty<string>()) });
        Assert.Contains("[03] ! warning: careful", mirror);
    }

    [Fact]
    public void Stops_at_first_failure_and_reports_it_loudly()
    {
        var (runner, mirror, proc) = Make(new()
        {
            ["fail"] = (7, Array.Empty<string>(), Array.Empty<string>()),
            ["never"] = (0, new[] { "should not run" }, Array.Empty<string>()),
        });
        var steps = new[]
        {
            new ScriptStep(1, "Fails", "fail", Array.Empty<string>()),
            new ScriptStep(2, "Never runs", "never", Array.Empty<string>()),
        };

        var results = runner.RunAll(steps);

        Assert.Single(results);
        Assert.Equal(7, results[0].ExitCode);
        Assert.DoesNotContain("never", proc.Calls.Select(c => c.command));
        Assert.Contains(mirror, l => l.Contains("FAILED (exit 7)"));
    }

    [Fact]
    public void Passes_arguments_through_to_the_process()
    {
        var (runner, _, proc) = Make(new()
        {
            ["wsl.exe"] = (0, Array.Empty<string>(), Array.Empty<string>()),
        });
        runner.RunAll(new[] { new ScriptStep(1, "In distro", "wsl.exe", new[] { "--", "bash", "-c", "echo hi" }) });
        Assert.Equal(new[] { "--", "bash", "-c", "echo hi" }, proc.Calls.Single().args);
    }
}

public class ParameterCollectorTests
{
    // A validator with teeth only exists for real parameters (data_disk today); the yes/no
    // tests supply their own inline rule — no production dead code for #90's future parameter.
    private static string? YesNo(string value) => value is "y" or "n" ? null : "answer y or n";

    [Fact]
    public void Empty_answer_takes_the_default()
    {
        var collector = new ParameterCollector(_ => "");
        var answers = collector.Collect(new[]
        {
            new ParameterSpec("join_lan", "Join?", "y", YesNo),
        });
        Assert.Equal("y", answers["join_lan"]);
    }

    [Fact]
    public void Invalid_answer_is_reasked_until_valid()
    {
        var queue = new Queue<string?>(new string?[] { "maybe", "n" });
        var collector = new ParameterCollector(_ => queue.Dequeue());
        var answers = collector.Collect(new[]
        {
            new ParameterSpec("join_lan", "Join?", "y", YesNo),
        });
        Assert.Equal("n", answers["join_lan"]);
        Assert.Empty(queue); // both answers consumed: the invalid one was re-asked
    }

    [Fact]
    public void No_default_and_no_answer_is_a_loud_error()
    {
        var collector = new ParameterCollector(_ => "");
        Assert.Throws<InvalidOperationException>(() =>
            collector.Collect(new[] { new ParameterSpec("data_disk", "Which disk?", null) }));
    }

    [Fact]
    public void Disk_validation_accepts_drive_paths_and_rejects_junk()
    {
        Assert.Null(ParameterCollector.ValidateDiskPath("D:\\"));
        Assert.Null(ParameterCollector.ValidateDiskPath("/data")); // POSIX roots (Linux wizard path)
        Assert.NotNull(ParameterCollector.ValidateDiskPath("not a path"));
        Assert.NotNull(ParameterCollector.ValidateDiskPath("/")); // bare root is refused on purpose
    }

    [Fact]
    public void Parameters_round_trip_as_json()
    {
        string path = Path.Combine(Path.GetTempPath(), $"wsparams-{Guid.NewGuid():N}.json");
        try
        {
            ParameterCollector.WriteParameters(new Dictionary<string, string> { ["data_disk"] = "D:\\" }, path);
            var parsed = System.Text.Json.JsonSerializer
                .Deserialize<Dictionary<string, string>>(File.ReadAllText(path))!;
            Assert.Equal("D:\\", parsed["data_disk"]);
        }
        finally
        {
            File.Delete(path);
        }
    }
}

public class PhaseHandoffTests
{
    [Fact]
    public void Python_probe_runs_python_INSIDE_the_distro_not_wsl_version()
    {
        var proc = new FakeProcess(new() { ["wsl.exe"] = (0, new[] { "Python 3.12.4" }, Array.Empty<string>()) });
        Assert.True(new PhaseHandoff(proc, _ => { }).PythonAvailableInWsl());
        // The regression this pins: `wsl.exe --version` would only prove WSL exists.
        Assert.Equal(new[] { "--", "python3", "--version" }, proc.Calls.Single().args);
    }

    [Fact]
    public void Python_unavailable_when_distro_probe_fails()
    {
        var proc = new FakeProcess(new Dictionary<string, (int, string[], string[])>());
        Assert.False(new PhaseHandoff(proc, _ => { }).PythonAvailableInWsl());
    }

    [Fact]
    public void Tui_handoff_translates_both_paths_then_launches_python_in_the_distro()
    {
        var mirror = new List<string>();
        var proc = new ArgAwareProcess((cmd, args) =>
        {
            if (args.Count > 0 && args[0] == "wslpath")
                return (0, new[] { "/mnt/c/" + args[2][2..].TrimStart('\\').Replace('\\', '/') }); // C:\x\y -> /mnt/c/x/y
            return (0, new[] { "tui ran" }); // wsl.exe -- python3 …
        });
        var handoff = new PhaseHandoff(proc, mirror.Add);

        int exit = handoff.HandOffToPythonTuiInWsl(
            @"C:\repo\installer\python\tui.py", @"C:\repo\params.json");

        Assert.Equal(0, exit);
        Assert.Equal(3, proc.Calls.Count);
        Assert.Equal(new[] { "wslpath", "-u", @"C:\repo\installer\python\tui.py" }, proc.Calls[0].args);
        Assert.Equal(new[] { "wslpath", "-u", @"C:\repo\params.json" }, proc.Calls[1].args);
        Assert.Equal("wsl.exe", proc.Calls[2].command);
        Assert.Equal(new[]
        {
            "--", "python3", "/mnt/c/repo/installer/python/tui.py", "--parameters", "/mnt/c/repo/params.json",
            "--journey", "windows",
        }, proc.Calls[2].args);
        Assert.Contains(mirror, l => l.Contains("handing the journey to the Python installer TUI"));
        Assert.Contains("tui ran", mirror);
    }

    [Fact]
    public void Tui_handoff_stops_loudly_when_a_path_cannot_be_translated()
    {
        var mirror = new List<string>();
        var proc = new FakeProcess(new() { ["wsl.exe"] = (1, Array.Empty<string>(), Array.Empty<string>()) });
        var handoff = new PhaseHandoff(proc, mirror.Add);

        int exit = handoff.HandOffToPythonTuiInWsl(@"C:\x\tui.py", @"C:\x\params.json");

        Assert.Equal(1, exit);
        Assert.Contains(mirror, l => l.Contains("could not translate a Windows path") && l.Contains("nothing further is installed"));
        // Only translations ran — the TUI was never launched.
        Assert.All(proc.Calls, c => Assert.Equal("wslpath", c.args[0]));
    }

    sealed class FakeWebHost : IWebUiHost
    {
        public string? Shown, Opened;
        public void Show(string url) => Shown = url;
        public void OpenInBrowser(string url) => Opened = url;
    }

    [Fact]
    public void Web_handoff_shows_the_webview_then_opens_the_browser_at_the_same_url()
    {
        var mirror = new List<string>();
        var handoff = new PhaseHandoff(new FakeProcess(new Dictionary<string, (int, string[], string[])>()), mirror.Add);
        var host = new FakeWebHost();

        handoff.HandOffToWeb("https://wordslab.local/", host);

        Assert.Equal("https://wordslab.local/", host.Shown);
        Assert.Equal("https://wordslab.local/", host.Opened);
        // The handoff says where the install continues — it does not claim the core is reachable
        // (reachability is the front door's concern, #88).
        Assert.Contains(mirror, l => l.Contains("continues in the dashboard at: https://wordslab.local/"));
    }
}
