using Wordslab.Wizard.Core;

// Windows-specific numbered scripts 1–3 (everything WSL-specific up to the first step shared
// with the Linux install) live here as C# classes. Their real content is ticket #88's home; the
// visible placeholder commands say so. Steps 4–6 are shared with Linux and run as their distro
// script FILES — see the DistroShellScript subclasses below.

namespace Wordslab.Wizard.Core.Scripts;

public sealed class Script01NetworkReachability : NumberedScript
{
    public override int Number => 1;
    public override string Title => "Check the internet connection";

    public override Task<IReadOnlyList<Command>> PlanAsync(InstallContext ctx) => Task.FromResult<IReadOnlyList<Command>>(
        new[]
        {
            new Command("pwsh",
                new[] { "-NoProfile", "-Command", "Write-Output 'reachability check: placeholder until #88'" },
                "Checking the internet connection"),
        });
}

public sealed class Script02WslDistroDisks : NumberedScript
{
    public override int Number => 2;
    public override string Title => "Turn on Windows' built-in Linux";

    public override Task<IReadOnlyList<Command>> PlanAsync(InstallContext ctx) => Task.FromResult<IReadOnlyList<Command>>(
        new[]
        {
            // #88: the real flow — enable WSL, register the Wordslab distro, attach the data
            // disks from ctx.Parameters["data_disk"], each as its own reported command.
            new Command("pwsh",
                new[] { "-NoProfile", "-Command", "Write-Output 'wsl bootstrap: placeholder until #88'" },
                "Turning on Windows' built-in Linux and preparing the Wordslab virtual machine"),
        });
}

public sealed class Script03UvPythonInDistro : NumberedScript
{
    public override int Number => 3;
    public override string Title => "Install the Wordslab engine (Python)";

    public override Task<IReadOnlyList<Command>> PlanAsync(InstallContext ctx) => Task.FromResult<IReadOnlyList<Command>>(
        new[]
        {
            // #88: wsl -- bash -c "curl -LsSf https://astral.sh/uv/install.sh | sh" and friends.
            new Command(Wsl.Exe,
                new[] { "--", "bash", "-c", "echo 'uv bootstrap: placeholder until #88'" },
                "Installing the Wordslab engine (Python)"),
        });
}

public sealed class Script04DataVolumes : DistroShellScript
{
    public override int Number => 4;
    public override string Title => "Create Wordslab's Linux disks on your drives";
    protected override string ScriptFile => "distro/04-data-volumes.sh";
}

public sealed class Script05FirstPlatformCore : DistroShellScript
{
    public override int Number => 5;
    public override string Title => "Install the Wordslab core programs";
    protected override string ScriptFile => "distro/05-first-core.sh";
}

public sealed class Script06FrontDoor : DistroShellScript
{
    public override int Number => 6;
    public override string Title => "Open your Wordslab home page (wordslab.local)";
    protected override string ScriptFile => "distro/06-front-door.sh";
}
