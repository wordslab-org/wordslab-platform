// The single moment this wizard ever needs Windows admin: switching Windows' built-in Linux on
// for the first time (#88 ruling). The window ASKS WINDOWS directly by relaunching itself
// elevated — one UAC dialog, never a console window ("console windows are banned" is absolute).
// Lives in Core so the rule sits with the other journey rules, not in the UI it drives.

using System.Security.Principal;

namespace Wordslab.Wizard.Core;

[System.Runtime.Versioning.SupportedOSPlatform("windows")] // Windows-only machinery, like the journey it guards
public static class Elevation
{
    /// <summary>Is the current process running with Windows admin?</summary>
    public static bool IsElevated()
    {
        using WindowsIdentity identity = WindowsIdentity.GetCurrent();
        return new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator);
    }

    /// <summary>Relaunch this very executable elevated (Windows shows the one UAC prompt).
    /// Returns false when the approval was declined — the caller then says so plainly.</summary>
    public static bool RelaunchSelfElevated()
    {
        try
        {
            System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
            {
                FileName = Environment.ProcessPath!,
                UseShellExecute = true,
                Verb = "runas", // the one UAC prompt Windows itself shows
            });
            return true;
        }
        catch (System.ComponentModel.Win32Exception)
        {
            return false; // the approval was declined — say so plainly
        }
    }
}
