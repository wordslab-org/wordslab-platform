using System.Text;

// Windows-specific numbered scripts 1–3 (everything "Windows' built-in Linux" specific up to the
// first step shared with the Linux install) live here as C# classes — no script files, the classes
// ARE the readable plan. Steps 4–6 are shared with Linux and run as their distro script FILES.
//
// #88 design ruling (recorded on the ticket): nothing here needs admin on a machine that already
// has Windows' built-in Linux. The Wordslab virtual machine and every Linux disk are created with
// `wsl --import` (the proven wordslab-notebooks mechanism): WSL itself places and manages a
// dynamic ext4.vhdx inside a plain folder on the chosen drive, auto-attached at every future
// start — no diskpart, no mkfs, no `wsl --mount` (which needs admin AND detaches at every reboot).
// Data reaches the app VM via `mount --bind` through /mnt/wsl, which WSL shares across distros.
// Only switching the feature on the very first time elevates, via the wizard relaunching ITSELF
// elevated (one UAC prompt, never a console window).
//
// NOTE on the literals: $$""" with {{holes}} — a single-$ interpolated raw string would turn every
// PowerShell { } into an interpolation hole (CS9006). The double-$ form keeps script braces literal.

namespace Wordslab.Wizard.Core.Scripts;

/// <summary>Contract (as documented per #88): in — nothing (parameters for paths only); out —
/// one loud line per target + a final human sentence; exit — 0 both reachable · 1 anything
/// unreachable (journey stops); re-run — read-only probe, always safe. Streams: every line
/// mirrored by the runner, stderr prefixed "!".</summary>
public sealed class Script01NetworkReachability : NumberedScript
{
    public override int Number => 1;
    public override string Title => "Check the internet connection";

    public override Task<IReadOnlyList<Command>> PlanAsync(InstallContext ctx) => Task.FromResult<IReadOnlyList<Command>>(
        new[]
        {
            // HTTPS HEAD on both targets, PS 5.1-compatible (TLS 1.2 set explicitly). Loud per
            // target either way; a failure exits non-zero so the runner stops the journey.
            new Command(PowerShellHost.Resolve(),
                new[]
                {
                    "-NoProfile", "-Command",
                    """
                    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;
                    $fail = $false;
                    foreach ($target in 'https://github.com', 'https://pypi.org') {
                      try {
                        $r = Invoke-WebRequest -Method Head -UseBasicParsing -TimeoutSec 20 $target;
                        Write-Output (([uri]$target).DnsSafeHost + ': reachable (HTTP ' + $r.StatusCode + ')')
                      } catch {
                        Write-Error (([uri]$target).DnsSafeHost + ': NOT reachable - ' + $_.Exception.Message);
                        $fail = $true
                      }
                    }
                    if ($fail) { Write-Error 'Wordslab needs github.com and pypi.org to be reachable. Check the connection, then press Start install again.'; exit 1 }
                    Write-Output 'Internet connection OK - github.com and pypi.org reachable.'
                    """
                },
                "Checking the internet connection"),
        });
}

/// <summary>Switches Windows' built-in Linux on, then imports the named Wordslab virtual machine.
/// Contract: in — install_dir (parameters); out — one state line per phase; exit — 0 feature on +
/// VM present · 3 feature not enabled (needs Windows admin or a restart) · other non-zero = failed,
/// journey stops; re-run — every phase guarded ("already switched on", "keeping it"), never
/// re-downloads a cached rootfs, never recreates the VM. The exit-3 code is what lets the window
/// ask Windows for admin once (one UAC) instead of nagging on unrelated failures.</summary>
public sealed class Script02WslFeatureAndVm : NumberedScript
{
    /// <summary>Documented exit: the feature switch itself failed while not elevated or not
    /// yet rebooted — the ONLY condition for which the window may ask Windows for admin.</summary>
    public const int ExitCodeNeedsAdminOrRestart = 3;

    public override int Number => 2;
    public override string Title => "Turn on Windows' built-in Linux";

    /// <summary>The Ubuntu 24.04 rootfs the Wordslab virtual machine is imported from — live-verified
    /// URL, pinned at implementation (2026-10-24), never from memory.</summary>
    public const string UbuntuRootfsUrl =
        "https://partner-images.canonical.com/oci/noble/current/ubuntu-noble-oci-amd64-root.tar.gz";

    public override Task<IReadOnlyList<Command>> PlanAsync(InstallContext ctx)
    {
        string installDir = InstallDirs.ProgramFolderOrThrow(ctx.Parameters);
        string vmDir = $@"{installDir}\virtual-machines\{Wsl.Distro}";
        string cacheDir = $@"{installDir}\cache";

        // Guarded inline (like every step here): re-running this step changes nothing when the
        // feature and the virtual machine already exist — "already switched on", "keeping it".
        string ensureFeature =
            """
            $ok = $false;
            try { wsl --status *>$null; $ok = ($LASTEXITCODE -eq 0) } catch {}
            if ($ok) { Write-Output "Windows' built-in Linux is already switched on - nothing to do." }
            else {
              Write-Output "Windows' built-in Linux is not switched on yet - Wordslab is switching it on now.";
              wsl --install --no-distribution;
              $ok = $false;
              try { wsl --status *>$null; $ok = ($LASTEXITCODE -eq 0) } catch {}
              if (-not $ok) {
                  Write-Error 'Windows needs Windows admin approval (and possibly one restart) to finish switching on its built-in Linux. Nothing else was changed.';
                  exit 3   // = Script02WslFeatureAndVm.ExitCodeNeedsAdminOrRestart (contract above)
              }
              Write-Output "Windows' built-in Linux is switched on."
            }
            """;

        // Import runs as root inside the new machine; /etc/wsl.conf turns systemd on and cuts
        // interop (the VM can never call Windows programs). automount stays on for now so the
        // core-staging step can read the installer payload - ticket #93 owns the default-deny
        // re-home of that (recorded on the ticket).
        string ensureVm =
            $$"""
            wsl -d {{Wsl.Distro}} -e /bin/true 2>$null;
            if ($LASTEXITCODE -eq 0) {
              Write-Output 'The Wordslab virtual machine is already installed - keeping it.'
            } else {
              Write-Output 'Creating the Wordslab virtual machine - the download takes a few minutes the first time.';
              New-Item -ItemType Directory -Force '{{cacheDir}}', '{{vmDir}}' | Out-Null;
              $tar = Join-Path '{{cacheDir}}' 'ubuntu-noble-oci-amd64-root.tar.gz';
              if (-not (Test-Path $tar)) { curl.exe -sSL -o $tar '{{UbuntuRootfsUrl}}' };
              wsl --import {{Wsl.Distro}} '{{vmDir}}' $tar;
              if ($LASTEXITCODE -ne 0) { Write-Error 'The Wordslab virtual machine could not be created - see the lines above.'; exit 1 };
              wsl -d {{Wsl.Distro}} -- sh -c "printf '[boot]\nsystemd = true\n\n[interop]\nenabled = false\nappendWindowsPath = false\n' > /etc/wsl.conf";
              wsl --shutdown;
              Write-Output 'The Wordslab virtual machine is ready.'
            }
            """;

        return Task.FromResult<IReadOnlyList<Command>>(new[]
        {
            new Command(PowerShellHost.Resolve(), new[] { "-NoProfile", "-Command", ensureFeature },
                "Making sure Windows' built-in Linux is switched on"),
            new Command(PowerShellHost.Resolve(), new[] { "-NoProfile", "-Command", ensureVm },
                "Creating the Wordslab virtual machine (first time only)"),
        });
    }
}

/// <summary>Installs the Wordslab engine INSIDE the named VM. Contract: in — nothing; out —
/// version lines + a final human sentence; exit — non-zero = engine missing, journey stops;
/// re-run — the uv installer re-runs on purpose (it upgrades uv in place: this step IS the
/// engine layer of the update lane, ADR-0016 §8 host lane), uv python install is a no-op when
/// 3.12 is already present.</summary>
public sealed class Script03UvPythonInDistro : NumberedScript
{
    public override int Number => 3;
    public override string Title => "Install the Wordslab engine (Python)";

    /// <summary>The engine landing place (#88 ruling): uv in /usr/local/bin, uv-managed CPython
    /// and cache under /opt/wordslab. Ticket #62's core plugs into the same slot. The uv
    /// installer is NOT guarded away on re-runs — re-running this step updates uv itself.</summary>
    public const string EngineBody =
        """
        set -e
        if ! command -v curl >/dev/null 2>&1; then apt-get update -qq && apt-get install -y -qq curl ca-certificates; fi
        curl -LsSf https://astral.sh/uv/install.sh | sh -s -- --install-dir /usr/local/bin
        grep -q UV_PYTHON_INSTALL_DIR /etc/environment 2>/dev/null || printf 'UV_PYTHON_INSTALL_DIR=/opt/wordslab/python\nUV_CACHE_DIR=/opt/wordslab/uv-cache\n' >> /etc/environment
        export UV_PYTHON_INSTALL_DIR=/opt/wordslab/python UV_CACHE_DIR=/opt/wordslab/uv-cache
        uv python install 3.12
        UVV=$(uv --version | cut -d" " -f2)
        PYV=$(uv run --no-project --python 3.12 python -c 'import sys; print(sys.version.split()[0])')
        echo "Wordslab engine ready - uv $UVV and Python $PYV in the Wordslab virtual machine."
        """;

    public override Task<IReadOnlyList<Command>> PlanAsync(InstallContext ctx) => Task.FromResult<IReadOnlyList<Command>>(
        new[] { Wsl.RunBashInline(EngineBody, "Installing the Wordslab engine (uv and Python) inside the virtual machine") });
}

/// <summary>Windows half: create one Wordslab Linux disk per enabled drive (host commands below);
/// distro half: the shared script bind-mounts them inside the VM. Contract: in — volume_&lt;DRIVE&gt;
/// keys + install_dir; out — per-disk state lines, then the shared script's lines; exit — 0 all
/// disks created+published · non-zero = a disk failed (journey stops) · 2 = shared script usage;
/// re-run — existing disks kept, publishes re-applied (idempotent). Full contract of the distro
/// half: header of scripts/distro/04-data-volumes.sh.</summary>
public sealed class Script04DataVolumes : DistroShellScript
{
    public override int Number => 4;
    public override string Title => "Create Wordslab's Linux disks on your drives";
    protected override string ScriptFile => "distro/04-data-volumes.sh";

    /// <summary>Minimal Alpine rootfs the Linux disks are imported from — live-verified URL,
    /// pinned at implementation (2026-10-24).</summary>
    public const string AlpineRootfsUrl =
        "https://dl-cdn.alpinelinux.org/alpine/v3.24/releases/x86_64/alpine-minirootfs-3.24.3-x86_64.tar.gz";

    /// <summary>One Wordslab Linux disk per enabled drive: a dedicated minimal WSL instance whose
    /// WSL-managed ext4.vhdx lives in <see cref="InstallDirs.VolumeDistroFolder"/> on that drive,
    /// publishing its /volume folder into the shared /mnt/wsl. Guarded: a re-run keeps existing
    /// disks untouched (the data-volume invariant, ADR-0014 §7). The /mnt/wsl publish is re-run
    /// outside the guard because WSL re-attaches instances at every start but bind mounts do not
    /// survive — idempotent re-publish, never a silent skip. After writing wsl.conf the instance
    /// is TERMINATED (config applies at its next start); the publish line then starts it again.
    /// (Re-binding after a whole-WSL shutdown at every Wordslab launch is the resident launcher's
    /// job — ticket #94, recorded on #88.)</summary>
    private static IEnumerable<Command> DiskCommands(InstallContext ctx)
    {
        string installDir = InstallDirs.ProgramFolderOrThrow(ctx.Parameters);
        string cacheDir = $@"{installDir}\cache";
        foreach (var (drive, folder) in InstallDirs.EnabledVolumes(ctx.Parameters))
        {
            string name = InstallDirs.VolumeDistroName(drive);
            string dir = InstallDirs.VolumeDistroFolder(folder, drive);
            string letter = drive.TrimEnd(':', '\\').ToUpperInvariant();
            yield return new Command(PowerShellHost.Resolve(),
                new[]
                {
                    "-NoProfile", "-Command",
                    $$"""
                    wsl -d {{name}} -e /bin/true 2>$null;
                    if ($LASTEXITCODE -eq 0) {
                      Write-Output 'The Wordslab Linux disk on drive {{letter}}: is already there - keeping it.'
                    } else {
                      Write-Output 'Creating the Wordslab Linux disk on drive {{letter}}:';
                      New-Item -ItemType Directory -Force '{{dir}}', '{{cacheDir}}' | Out-Null;
                      $tar = Join-Path '{{cacheDir}}' 'alpine-minirootfs.tar.gz';
                      if (-not (Test-Path $tar)) { curl.exe -sSL -o $tar '{{AlpineRootfsUrl}}' };
                      wsl --import {{name}} '{{dir}}' $tar;
                      if ($LASTEXITCODE -ne 0) { Write-Error 'The Wordslab Linux disk on drive {{letter}}: could not be created - see the lines above.'; exit 1 };
                      wsl -d {{name}} -- sh -c "printf '[automount]\nenabled = false\n\n[interop]\nenabled = false\nappendWindowsPath = false\n' > /etc/wsl.conf";
                      wsl --terminate {{name}};   // config applies at the instance's next start
                      Write-Output 'The Wordslab Linux disk on drive {{letter}}: is ready (its disk file lives in {{dir}})'
                    };
                    wsl -d {{name}} -- sh -c "mkdir -p /volume /mnt/wsl/{{name}}; mountpoint -q /mnt/wsl/{{name}} || mount --bind /volume /mnt/wsl/{{name}}";
                    if ($LASTEXITCODE -ne 0) { Write-Error 'The Wordslab Linux disk on drive {{letter}}: did not publish its data folder - press Start install again.'; exit 1 }
                    """
                },
                $"Creating the Wordslab Linux disk on drive {letter}:");
        }
    }

    public override async Task<IReadOnlyList<Command>> PlanAsync(InstallContext ctx) =>
        DiskCommands(ctx).Concat(await base.PlanAsync(ctx)).ToArray();
}

/// <summary>Shared script step — full contract in the script's own header (05-first-core.sh).</summary>
public sealed class Script05FirstPlatformCore : DistroShellScript
{
    public override int Number => 5;
    public override string Title => "Install the Wordslab core programs";
    protected override string ScriptFile => "distro/05-first-core.sh";
}

/// <summary>Distro half: shared script (contract in 06-front-door.sh's header); Windows half: an
/// after-the-script probe. Probe contract: in — nothing; out — the answered address line; exit —
/// 0 home page answers (and writes the handoff address file) · 1 no address or no answer, with a
/// plain sentence (red card, journey stops — never a fake green until #62/#92 land).</summary>
public sealed class Script06FrontDoor : DistroShellScript
{
    public override int Number => 6;
    public override string Title => "Open your Wordslab home page (wordslab.local)";
    protected override string ScriptFile => "distro/06-front-door.sh";

    /// <summary>The front door answers on the VM's own address for now (#88 ruling — mDNS naming
    /// and CA trust land with #92/#94). The probe writes the address file the window navigates to,
    /// then its own final line becomes the card's success sentence. The certificate callback is
    /// deliberately scoped to this single throwaway PowerShell process until #92's CA-trusted cert
    /// exists — no other traffic passes through it.</summary>
    private static Command FrontDoorProbeCommand(InstallContext ctx)
    {
        string urlFile = Path.Combine(
            Path.GetDirectoryName(ctx.ParametersFile) ?? ".", "wordslab-front-door.url");
        return new Command(PowerShellHost.Resolve(),
            new[]
            {
                "-NoProfile", "-Command",
                $$"""
                $ip = ((wsl -d {{Wsl.Distro}} -- hostname -I) | Out-String).Trim().Split(' ')[0];
                if (-not $ip) { Write-Error 'The Wordslab virtual machine did not report an address - press Start install again.'; exit 1 };
                $ok = $false;
                try {
                  [Net.ServicePointManager]::ServerCertificateValidationCallback = { $true };
                  $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 15 "https://$ip/";
                  $ok = ($r.StatusCode -eq 200)
                } catch {};
                if (-not $ok) { Write-Error 'The Wordslab home page did not answer yet - press Start install again; starting over is safe.'; exit 1 };
                Set-Content -LiteralPath '{{urlFile}}' -Value "https://$ip/";
                Write-Output "Wordslab home page answering at https://$ip/ - one port, one certificate."
                """
            },
            "Reaching the Wordslab home page from Windows");
    }

    public override async Task<IReadOnlyList<Command>> PlanAsync(InstallContext ctx) =>
        (await base.PlanAsync(ctx)).Append(FrontDoorProbeCommand(ctx)).ToArray();
}
