namespace Wordslab.Wizard.App;

/// <summary>One physical drive as the installer sees it: a row the user can switch off and
/// point at a folder. Every enabled drive gets one Wordslab Linux disk (VHDX) in that folder
/// (ADR-0014 §5 — a data volume per physical disk, named after the disk).
/// Plain settable properties on purpose: WinUI's generated XamlTypeInfo builds a factory and
/// Get/Set trampolines for row types used in DataTemplates — `required`/`init` members break
/// that generated code (CS9035/CS8852 in XamlTypeInfo.g.cs).</summary>
public sealed class DriveVm
{
    public string Drive { get; set; } = ""; // "C:"
    public long FreeGb { get; set; }
    public string DriveLabel => $"{Drive} — {FreeGb} GB free";
    public bool Enabled { get; set; } = true;
    public string Folder { get; set; } = "";
    // v1 fixed layout: the exact virtual Linux disk file shown on screen and created by #88.
    public string VhdxPath
    {
        get
        {
            char letter = Drive.Length > 0 ? char.ToLowerInvariant(Drive[0]) : '?';
            return $@"{Drive}\wordslab\wordslab-{letter}.vhdx";
        }
    }
}
