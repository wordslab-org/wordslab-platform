namespace Wordslab.Wizard.Core;

/// <summary>One numbered bootstrap script, expressed as a small class: the number, the title and
/// the commands it runs are readable top-to-bottom. The runner owns running, streaming and
/// stop-on-failure — script classes never call processes directly.</summary>
public abstract class NumberedScript
{
    public abstract int Number { get; }
    public abstract string Title { get; }

    /// <summary>The command lines this script runs, in order. Async only because a script may ask
    /// the distro to translate a path first (visible in the journey, never silent).</summary>
    public abstract Task<IReadOnlyList<Command>> PlanAsync(InstallContext ctx);
}

/// <summary>A script shared with the Linux install, run inside the distro as its numbered shell
/// FILE (so it stays runnable by hand there too).</summary>
public abstract class DistroShellScript : NumberedScript
{
    /// <summary>Relative to installer/scripts — e.g. "distro/04-data-volumes.sh".</summary>
    protected abstract string ScriptFile { get; }

    public override async Task<IReadOnlyList<Command>> PlanAsync(InstallContext ctx)
    {
        string windowsPath = ctx.DistroScript(ScriptFile);
        // Without WSL the path cannot translate; the step then fails loudly with the distro's own
        // error rather than silently skipping — nothing is ever hidden from the user.
        string distroPath = await ctx.WslPaths.ToDistroPathAsync(windowsPath) ?? windowsPath;
        return new[] { Wsl.RunBash(distroPath) };
    }
}

/// <summary>A shared script that runs as Python inside the distro — the shape ticket #88 moves
/// the numbered steps to (the same files the Linux TUI drives).</summary>
public abstract class DistroPythonScript : NumberedScript
{
    /// <summary>Relative to installer/python — e.g. "steps/step04_data_volumes.py".</summary>
    protected abstract string PythonFile { get; }

    public override async Task<IReadOnlyList<Command>> PlanAsync(InstallContext ctx)
    {
        string windowsPath = ctx.PythonScript(PythonFile);
        string distroPath = await ctx.WslPaths.ToDistroPathAsync(windowsPath) ?? windowsPath;
        return new[] { Wsl.RunPython(distroPath) };
    }
}
