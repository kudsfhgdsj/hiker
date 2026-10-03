// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for German (`de`).
class AppLocalizationsDe extends AppLocalizations {
  AppLocalizationsDe([String locale = 'de']) : super(locale);

  @override
  String get appTitle => 'hiker';

  @override
  String get loading => 'Lädt …';

  @override
  String get retry => 'Erneut versuchen';

  @override
  String get save => 'Speichern';

  @override
  String get saved => 'Gespeichert';

  @override
  String get cancel => 'Abbrechen';

  @override
  String get requiredField => 'Pflichtfeld';

  @override
  String get invalidNumber => 'Bitte eine gültige Zahl eingeben';

  @override
  String get loginTitle => 'Anmelden';

  @override
  String get registerTitle => 'Konto anlegen';

  @override
  String get serverUrl => 'Server-Adresse';

  @override
  String get serverUrlHint => 'https://hiker.example.org';

  @override
  String get serverUrlInvalid =>
      'Bitte eine Adresse mit http:// oder https:// eingeben';

  @override
  String get email => 'E-Mail';

  @override
  String get emailInvalid => 'Bitte eine gültige E-Mail-Adresse eingeben';

  @override
  String get password => 'Passwort';

  @override
  String get passwordTooShort => 'Mindestens 10 Zeichen';

  @override
  String get displayName => 'Anzeigename';

  @override
  String get loginAction => 'Anmelden';

  @override
  String get registerAction => 'Konto anlegen';

  @override
  String get goToRegister => 'Noch kein Konto? Konto anlegen';

  @override
  String get goToLogin => 'Schon ein Konto? Anmelden';

  @override
  String get logout => 'Abmelden';

  @override
  String get profileTitle => 'Profil';

  @override
  String get profileIntro =>
      'Diese Angaben sind freiwillig. Sie dienen nur der Schätzung des Kalorienverbrauchs und sind für niemanden sonst sichtbar.';

  @override
  String get weightKg => 'Gewicht (kg)';

  @override
  String get birthYear => 'Geburtsjahr';

  @override
  String get sex => 'Geschlecht';

  @override
  String get sexFemale => 'weiblich';

  @override
  String get sexMale => 'männlich';

  @override
  String get sexTrans => 'trans';

  @override
  String get sexUndisclosed => 'keine Angabe';

  @override
  String get sexNotSet => 'nicht festgelegt';

  @override
  String get maxHeartRate => 'Maximale Herzfrequenz';

  @override
  String get restingHeartRate => 'Ruheherzfrequenz';

  @override
  String signedInAs(String name) {
    return 'Angemeldet als $name';
  }

  @override
  String get roleAdmin => 'Administrator';

  @override
  String get noModulesTitle => 'Noch nichts zu sehen';

  @override
  String get noModulesBody =>
      'Auf diesem Server ist kein Modul aktiv, das diese App kennt.';

  @override
  String get errorNetwork =>
      'Der Server ist nicht erreichbar. Bitte Verbindung und Adresse prüfen.';

  @override
  String get errorInvalidCredentials => 'E-Mail oder Passwort ist falsch.';

  @override
  String get errorEmailTaken => 'Diese E-Mail-Adresse ist schon registriert.';

  @override
  String get errorRegistrationClosed =>
      'Auf diesem Server können keine neuen Konten angelegt werden.';

  @override
  String get errorRateLimited => 'Zu viele Versuche. Bitte kurz warten.';

  @override
  String get errorValidation =>
      'Die Eingaben wurden vom Server nicht angenommen.';

  @override
  String get errorSessionExpired =>
      'Die Anmeldung ist abgelaufen. Bitte neu anmelden.';

  @override
  String get errorUnknown =>
      'Etwas ist schiefgegangen. Bitte später erneut versuchen.';
}
