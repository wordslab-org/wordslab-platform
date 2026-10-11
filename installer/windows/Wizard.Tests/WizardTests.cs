using Wordslab.Wizard;
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
    [Fact]
    public void Empty_answer_takes_the_default()
    {
        var collector = new ParameterCollector(_ => "");
        var answers = collector.Collect(new[]
        {
            new ParameterSpec("join_lan", "Join?", "y", ParameterCollector.ValidateYesNo),
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
            new ParameterSpec("join_lan", "Join?", "y", ParameterCollector.ValidateYesNo),
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
        Assert.NotNull(ParameterCollector.ValidateDiskPath("not a path"));
    }

    [Fact]
    public void Parameters_round_trip_as_json()
    {
        string path = Path.Combine(Path.GetTempPath(), $"wsparams-{Guid.NewGuid():N}.json");
        try
        {
            ParameterCollector.WriteParameters(new Dictionary<string, string> { ["data_disk"] = "D:\\" }, path);
            string json = File.ReadAllText(path);
            Assert.Contains("\"data_disk\"", json);
            Assert.Contains("D:\\\\", json);
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
    public void Python_available_when_version_probe_exits_zero()
    {
        var proc = new FakeProcess(new() { ["python3"] = (0, new[] { "Python 3.12.4" }, Array.Empty<string>()) });
        Assert.True(new PhaseHandoff(proc, _ => { }).PythonAvailable());
    }

    [Fact]
    public void Python_unavailable_when_probe_fails()
    {
        var proc = new FakeProcess(new Dictionary<string, (int, string[], string[])>());
        Assert.False(new PhaseHandoff(proc, _ => { }).PythonAvailable());
    }

    [Fact]
    public void Tui_handoff_launches_the_tui_with_the_parameters_file()
    {
        var mirror = new List<string>();
        var proc = new FakeProcess(new() { ["python3"] = (0, new[] { "tui ran" }, Array.Empty<string>()) });
        var handoff = new PhaseHandoff(proc, mirror.Add);

        int exit = handoff.HandOffToPythonTui("python3", "installer/tui.py", "/tmp/params.json");

        Assert.Equal(0, exit);
        var call = proc.Calls.Single();
        Assert.Equal("python3", call.command);
        Assert.Equal(new[] { "installer/tui.py", "--parameters", "/tmp/params.json" }, call.args);
        Assert.Contains(mirror, l => l.Contains("handing the journey to the Python installer TUI"));
        Assert.Contains("tui ran", mirror);
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
        Assert.Contains(mirror, l => l.Contains("https://wordslab.local/"));
    }
}
