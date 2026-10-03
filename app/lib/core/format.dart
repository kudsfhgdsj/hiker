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

  static final _dateTime = DateFormat('dd.MM.yyyy HH:mm', 'de');

  static String dateTime(DateTime date) => _dateTime.format(date.toLocal());

  static final _time = DateFormat('HH:mm', 'de');

  static String time(DateTime date) => _time.format(date.toLocal());

  /// 135 → "2 h 15 min".
  static String duration(int? minutes) {
    if (minutes == null) return '–';
    final hours = minutes ~/ 60;
    final rest = minutes % 60;
    if (hours == 0) return '$rest min';
    return rest == 0 ? '$hours h' : '$hours h $rest min';
  }

  /// 1112 → "1,1 km", 450 → "450 m".
  static String distance(num? meters) {
    if (meters == null) return '–';
    if (meters < 1000) return '${_decimal.format(meters.round())} m';
    return '${_oneDecimal.format(meters / 1000)} km';
  }

  static String meters(num? value) =>
      value == null ? '–' : '${_decimal.format(value.round())} m';

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
