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
        // A checkout with CRLF (Git for Windows' default core.autocrlf) makes bash die with
        // "set: pipefail: invalid option name" — a message that blames the wrong thing. Name
        // the real cause here instead (the .gitattributes file keeps future checkouts LF).
        if (File.Exists(windowsPath) && File.ReadAllText(windowsPath).Contains("\r\n"))
            throw new InvalidOperationException(
                $"'{Path.GetFileName(windowsPath)}' has Windows line endings (CRLF) and bash cannot run it. " +
                "Re-checkout the repository with its .gitattributes in place: git rm --cached -r . then git reset --hard.");
        // NEVER fall back to the raw Windows path: wsl.exe strips the backslashes on its way to
        // Linux ("C:Userslaure…", exit 127 — live bug) and the error blames the wrong thing.
        string distroPath = await ctx.WslPaths.ToDistroPathAsync(windowsPath)
            ?? throw new InvalidOperationException(
                $"the installer cannot reach '{windowsPath}' from inside the Wordslab virtual machine " +
                "(only paths on a Windows drive can be shared with it)");
        // #88: the shared scripts read the same parameters contract the wizard wrote — the file
        // crosses the distro boundary translated, exactly like the script path.
        string paramsDistro = await ctx.WslPaths.ToDistroPathAsync(ctx.ParametersFile)
            ?? throw new InvalidOperationException(
                $"the installer cannot reach the parameters file '{ctx.ParametersFile}' from inside the virtual machine");
        return new[] { Wsl.RunBash(distroPath, new[] { "--parameters", paramsDistro }) };
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
