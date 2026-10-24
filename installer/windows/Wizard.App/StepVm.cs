using System.ComponentModel;

namespace Wordslab.Wizard.App;

/// <summary>One numbered journey step as the UI sees it: number, title, live status and the
/// streaming tail of its output. The tail IS the log: it shows the last few lines live, and a
/// "··· more" tail click reveals the whole log ("··· show less" folds it back).</summary>
public sealed class StepVm : INotifyPropertyChanged
{
    private string _statusText = ""; // blank until it starts — "ready" read as odd
    private bool _isRunning;
    private bool _isFailed;
    private bool _isDone;
    private bool _expanded;
    private readonly List<string> _lines = new();

    public StepVm(int number, string title)
    {
        Number = number;
        Title = title;
    }

    public int Number { get; }
    public string NumberText => Number.ToString();
    public string Title { get; }
    public bool HasLog => _lines.Count > 0;

    public string StatusText
    {
        get => _statusText;
        set { _statusText = value; Raise(nameof(StatusText)); }
    }

    public bool IsRunning
    {
        get => _isRunning;
        set { _isRunning = value; Raise(nameof(IsRunning)); }
    }

    public bool IsFailed
    {
        get => _isFailed;
        set { _isFailed = value; Raise(nameof(IsFailed)); }
    }

    public bool IsDone
    {
        get => _isDone;
        set { _isDone = value; Raise(nameof(IsDone)); }
    }

    public bool Expanded
    {
        get => _expanded;
        private set { _expanded = value; Raise(nameof(Expanded)); Raise(nameof(DisplayLog)); }
    }

    public string DisplayLog => _expanded ? BuildFull() : BuildPreview();

    private const int PreviewLines = 3;   // the "two or three streaming lines" on the card
    private const int MaxLogLines = 400;  // the journey mirrors everything; the card keeps the tail

    public void AppendLog(string line)
    {
        _lines.Add(line);
        if (_lines.Count > MaxLogLines) _lines.RemoveRange(0, _lines.Count - MaxLogLines);
        Raise(nameof(HasLog));
        Raise(nameof(DisplayLog));
    }

    public void ToggleLog() => Expanded = !_expanded;

    /// <summary>A finished step shows its own last meaningful report line as the result —
    /// "done" said nothing; the command's final sentence does.</summary>
    public void MarkSuccess()
    {
        string last = "";
        for (int i = _lines.Count - 1; i >= 0; i--)
        {
            string l = _lines[i].Trim();
            if (l.Length > 0 && !l.StartsWith("!") && l != StatusText) { last = l; break; }
        }
        IsRunning = false;
        IsDone = true;
        StatusText = last.Length > 0 ? last : "completed";
    }

    private string BuildPreview()
    {
        var tail = _lines.Count <= PreviewLines ? _lines : _lines.Skip(_lines.Count - PreviewLines);
        string text = string.Join("\n", tail);
        if (_lines.Count > PreviewLines) text += "   ··· more";
        return text;
    }

    private string BuildFull()
    {
        string text = string.Join("\n", _lines);
        if (_lines.Count > PreviewLines) text += "\n··· show less";
        return text;
    }

    public event PropertyChangedEventHandler? PropertyChanged;
    private void Raise(string name) => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
}
