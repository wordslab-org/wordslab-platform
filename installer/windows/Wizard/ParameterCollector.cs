using System.Globalization;
using System.Text.Json;

namespace Wordslab.Wizard;

/// <summary>One install parameter the phase-1 wizard collects (ADR-0014 §3: "collects the initial
/// parameters"). Every parameter is surfaced with an explanation and a default — no silent decisions.</summary>
public sealed record ParameterSpec(
    string Key,
    string Question,
    string? DefaultValue,
    Func<string, string?>? Validate = null);

/// <summary>
/// Collects install parameters from the console (or an injected responder, the test seam) and writes
/// them to a parameters file the later phases read. Defaults are shown and explained; invalid answers
/// are re-asked loudly.
/// </summary>
public sealed class ParameterCollector
{
    private readonly Func<ParameterSpec, string?> _respond;

    /// <summary><paramref name="respond"/> returns the raw answer for a spec, or null for "accept default".</summary>
    public ParameterCollector(Func<ParameterSpec, string?> respond) => _respond = respond;

    /// <summary>Accepts a Windows drive root (D:\) or a POSIX absolute path — the wizard runs on the
    /// Windows host but the contract is tested cross-platform.</summary>
    public static string? ValidateDiskPath(string value)
    {
        bool windowsDrive = value.Length is 3 && char.IsLetter(value[0]) && value[1] == ':' && (value[2] == '\\' || value[2] == '/');
        bool posixRoot = value.Length > 1 && value[0] == '/';
        return windowsDrive || posixRoot ? null : "not a valid drive path (e.g. D:\\)";
    }

    public static string? ValidateYesNo(string value) =>
        value is "y" or "n" or "yes" or "no" ? null : "answer y or n";

    public IReadOnlyDictionary<string, string> Collect(IReadOnlyList<ParameterSpec> specs)
    {
        var answers = new Dictionary<string, string>();
        foreach (var spec in specs)
        {
            while (true)
            {
                string prompt = spec.DefaultValue is null
                    ? $"{spec.Question}: "
                    : $"{spec.Question} [default: {spec.DefaultValue}]: ";
                Console.Write(prompt);
                string? raw = _respond(spec);
                string value = string.IsNullOrWhiteSpace(raw)
                    ? spec.DefaultValue ?? throw new InvalidOperationException($"parameter '{spec.Key}' has no default and no answer")
                    : raw.Trim();
                string? error = spec.Validate?.Invoke(value);
                if (error is null)
                {
                    answers[spec.Key] = value;
                    break;
                }
                Console.WriteLine($"  not valid: {error}");
            }
        }
        return answers;
    }

    /// <summary>Writes the collected parameters as JSON for the next phase to read.</summary>
    public static void WriteParameters(IReadOnlyDictionary<string, string> answers, string path)
    {
        var opts = new JsonSerializerOptions { WriteIndented = true };
        File.WriteAllText(path, JsonSerializer.Serialize(answers, opts));
    }
}
