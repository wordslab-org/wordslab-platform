namespace Wordslab.Wizard.Core;

/// <summary>Every remote location the journey actually FETCHES, with the step that uses it.
/// Step 1 probes exactly these — in an enterprise network the firewall must fail there, with the
/// blocked download named, not five steps later. The hosts only reached through redirects are
/// named in the failure message too: firewalls routinely allow github.com and block its file
/// hosts, and a HEAD on the redirecting URL cannot see that.</summary>
public static class JourneyEndpoints
{
    public sealed record Endpoint(string Url, string Purpose);

    public static readonly IReadOnlyList<Endpoint> All = new[]
    {
        new Endpoint("https://github.com/", "GitHub - uv's release downloads"),
        new Endpoint("https://pypi.org/simple/", "PyPI - the package index uv installs from"),
        new Endpoint(Scripts.Script03UvPythonInDistro.UvInstallerUrl, "uv's installer script (step 3)"),
        new Endpoint(Scripts.Script02WslFeatureAndVm.UbuntuRootfsUrl, "the Ubuntu root image of the Wordslab virtual machine (step 2)"),
        new Endpoint(Scripts.Script04DataVolumes.AlpineRootfsUrl, "the minimal root image of each Wordslab Linux disk (step 4)"),
    };

    /// <summary>Hosts behind redirects — never probed (no stable URL), always named when a probe
    /// fails, because blocking one of these looks exactly like "the installer is broken".</summary>
    public const string HostsToAllow =
        "github.com, objects.githubusercontent.com, release-assets.githubusercontent.com, " +
        "pypi.org, files.pythonhosted.org, astral.sh, partner-images.canonical.com, " +
        "dl-cdn.alpinelinux.org";
}
