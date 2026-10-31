namespace Wordslab.Wizard.App;

using Wordslab.Wizard.Core;

/// <summary>One physical drive as the installer sees it: a row the user can switch off and
/// point at a folder. Every enabled drive gets one Wordslab Linux disk in that folder
/// (ADR-0014 §5 — a data volume per physical disk, named after the disk). Since the #88
/// ruling each disk is a folder WSL manages: the ext4.vhdx lives inside it, created by
/// `wsl --import` — never a loose VHDX file the wizard would have to attach with admin.
/// Plain settable properties on purpose: WinUI's generated XamlTypeInfo builds a factory and
/// Get/Set trampolines for row types used in DataTemplates — `required`/`init` members break
/// that generated code (CS9035/CS8852 in XamlTypeInfo.g.cs).</summary>
public sealed class DriveVm
{
    public string Drive { get; set; } = ""; // "C:"
    public long FreeGb { get; set; }
    public string DriveLabel => FreeGb >= 0 ? $"{Drive} — {FreeGb} GB free" : $"{Drive} — drive busy, will be probed at install";
    public bool Enabled { get; set; } = true;
    public string Folder { get; set; } = "";
    // v1 fixed layout: the exact folder the install step creates on screen — WSL places and
    // manages the Linux disk (ext4.vhdx) inside it. One formula with the install steps (InstallDirs).
    public string DiskFolderPath
    {
        get => string.IsNullOrEmpty(Folder) ? "" : InstallDirs.VolumeDistroFolder(Folder, Drive);
    }
}
