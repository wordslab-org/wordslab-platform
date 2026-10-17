using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Data;

namespace Wordslab.Wizard.App;

/// <summary>Plain true→Visible converter — WinUI ships none, and the alternative would be
/// string tricks in the markup.</summary>
public sealed class BooleanToVisibilityConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language) =>
        value is true ? Visibility.Visible : Visibility.Collapsed;

    public object ConvertBack(object value, Type targetType, object parameter, string language) =>
        throw new NotSupportedException();
}
