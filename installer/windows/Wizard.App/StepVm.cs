using System.Collections.ObjectModel;
using System.ComponentModel;

namespace Wordslab.Wizard.App;

/// <summary>One numbered journey step as the UI sees it: number, title, live status and a
/// streaming log. The view binds to this; nothing else in the XAML knows about processes.</summary>
public sealed class StepVm : INotifyPropertyChanged
{
    private string _statusText = ""; // blank until it starts — "ready" read as odd
    private bool _isRunning;
    private bool _isFailed;
    private bool _isDone;
    private string _logText = "";

    public StepVm(int number, string title)
    {
        Number = number;
        Title = title;
    }

    public int Number { get; }
    public string NumberText => Number.ToString();
    public string Title { get; }
    public bool HasLog => LogText.Length > 0;

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

    public string LogText
    {
        get => _logText;
        private set { _logText = value; Raise(nameof(LogText)); Raise(nameof(HasLog)); }
    }

    private const int MaxLogLines = 400; // the journey mirrors everything; the card keeps the tail
    public void AppendLog(string line)
    {
        string text = LogText.Length == 0 ? line : LogText + "\n" + line;
        string[] lines = text.Split('\n');
        LogText = lines.Length <= MaxLogLines ? text : string.Join("\n", lines[^MaxLogLines..]);
    }

    public event PropertyChangedEventHandler? PropertyChanged;
    private void Raise(string name) => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
}
