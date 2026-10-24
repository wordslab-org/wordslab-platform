namespace Wordslab.Wizard.App;

/// <summary>One physical drive as the installer sees it: a row the user can switch off and
/// point at a folder. Every enabled drive gets one Wordslab Linux disk (VHDX) in that folder
/// (ADR-0014 §5 — a data volume per physical disk, named after the disk).</summary>
public sealed class DriveVm
{
    public required string Drive { get; init; } // "C:"
    public required long FreeGb { get; init; }
    public string DriveLabel => $"{Drive} — {FreeGb} GB free";
    public bool Enabled { get; set; } = true;
    public string Folder { get; set; } = "";
}
