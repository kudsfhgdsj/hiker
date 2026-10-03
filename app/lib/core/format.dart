import 'package:intl/intl.dart';

/// German formatting of the numbers the app shows.
class Format {
  const Format._();

  static final _decimal = NumberFormat('#,##0.##', 'de');
  static final _oneDecimal = NumberFormat('#,##0.0', 'de');
  static final _money = NumberFormat('#,##0.00', 'de');
  static final _date = DateFormat('dd.MM.yyyy', 'de');

  /// 890 → "890 g", 1500 → "1,5 kg".
  static String weight(num? grams) {
    if (grams == null) return '–';
    if (grams.abs() < 1000) return '${_decimal.format(grams)} g';
    return '${_decimal.format(grams / 1000)} kg';
  }

  static String money(num amount, String currency) =>
      '${_money.format(amount)} $currency';

  static String number(num value) => _decimal.format(value);

  static String oneDecimal(num value) => _oneDecimal.format(value);

  static String date(DateTime date) => _date.format(date.toLocal());

  /// Text of a number field → number; accepts a comma as decimal separator.
  static double? parseNumber(String text) =>
      double.tryParse(text.trim().replaceAll(',', '.'));

  /// A number as the text of an input field, without a trailing ".0".
  static String input(num? value) {
    if (value == null) return '';
    return value == value.roundToDouble()
        ? value.round().toString()
        : value.toString().replaceAll('.', ',');
  }
}
