import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_de.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[Locale('de')];

  /// No description provided for @appTitle.
  ///
  /// In de, this message translates to:
  /// **'hiker'**
  String get appTitle;

  /// No description provided for @loading.
  ///
  /// In de, this message translates to:
  /// **'Lädt …'**
  String get loading;

  /// No description provided for @retry.
  ///
  /// In de, this message translates to:
  /// **'Erneut versuchen'**
  String get retry;

  /// No description provided for @save.
  ///
  /// In de, this message translates to:
  /// **'Speichern'**
  String get save;

  /// No description provided for @saved.
  ///
  /// In de, this message translates to:
  /// **'Gespeichert'**
  String get saved;

  /// No description provided for @cancel.
  ///
  /// In de, this message translates to:
  /// **'Abbrechen'**
  String get cancel;

  /// No description provided for @requiredField.
  ///
  /// In de, this message translates to:
  /// **'Pflichtfeld'**
  String get requiredField;

  /// No description provided for @invalidNumber.
  ///
  /// In de, this message translates to:
  /// **'Bitte eine gültige Zahl eingeben'**
  String get invalidNumber;

  /// No description provided for @loginTitle.
  ///
  /// In de, this message translates to:
  /// **'Anmelden'**
  String get loginTitle;

  /// No description provided for @registerTitle.
  ///
  /// In de, this message translates to:
  /// **'Konto anlegen'**
  String get registerTitle;

  /// No description provided for @serverUrl.
  ///
  /// In de, this message translates to:
  /// **'Server-Adresse'**
  String get serverUrl;

  /// No description provided for @serverUrlHint.
  ///
  /// In de, this message translates to:
  /// **'https://hiker.example.org'**
  String get serverUrlHint;

  /// No description provided for @serverUrlInvalid.
  ///
  /// In de, this message translates to:
  /// **'Bitte eine Adresse mit http:// oder https:// eingeben'**
  String get serverUrlInvalid;

  /// No description provided for @email.
  ///
  /// In de, this message translates to:
  /// **'E-Mail'**
  String get email;

  /// No description provided for @emailInvalid.
  ///
  /// In de, this message translates to:
  /// **'Bitte eine gültige E-Mail-Adresse eingeben'**
  String get emailInvalid;

  /// No description provided for @password.
  ///
  /// In de, this message translates to:
  /// **'Passwort'**
  String get password;

  /// No description provided for @passwordTooShort.
  ///
  /// In de, this message translates to:
  /// **'Mindestens 10 Zeichen'**
  String get passwordTooShort;

  /// No description provided for @displayName.
  ///
  /// In de, this message translates to:
  /// **'Anzeigename'**
  String get displayName;

  /// No description provided for @loginAction.
  ///
  /// In de, this message translates to:
  /// **'Anmelden'**
  String get loginAction;

  /// No description provided for @registerAction.
  ///
  /// In de, this message translates to:
  /// **'Konto anlegen'**
  String get registerAction;

  /// No description provided for @goToRegister.
  ///
  /// In de, this message translates to:
  /// **'Noch kein Konto? Konto anlegen'**
  String get goToRegister;

  /// No description provided for @goToLogin.
  ///
  /// In de, this message translates to:
  /// **'Schon ein Konto? Anmelden'**
  String get goToLogin;

  /// No description provided for @logout.
  ///
  /// In de, this message translates to:
  /// **'Abmelden'**
  String get logout;

  /// No description provided for @profileTitle.
  ///
  /// In de, this message translates to:
  /// **'Profil'**
  String get profileTitle;

  /// No description provided for @profileIntro.
  ///
  /// In de, this message translates to:
  /// **'Diese Angaben sind freiwillig. Sie dienen nur der Schätzung des Kalorienverbrauchs und sind für niemanden sonst sichtbar.'**
  String get profileIntro;

  /// No description provided for @weightKg.
  ///
  /// In de, this message translates to:
  /// **'Gewicht (kg)'**
  String get weightKg;

  /// No description provided for @birthYear.
  ///
  /// In de, this message translates to:
  /// **'Geburtsjahr'**
  String get birthYear;

  /// No description provided for @sex.
  ///
  /// In de, this message translates to:
  /// **'Geschlecht'**
  String get sex;

  /// No description provided for @sexFemale.
  ///
  /// In de, this message translates to:
  /// **'weiblich'**
  String get sexFemale;

  /// No description provided for @sexMale.
  ///
  /// In de, this message translates to:
  /// **'männlich'**
  String get sexMale;

  /// No description provided for @sexTrans.
  ///
  /// In de, this message translates to:
  /// **'trans'**
  String get sexTrans;

  /// No description provided for @sexUndisclosed.
  ///
  /// In de, this message translates to:
  /// **'keine Angabe'**
  String get sexUndisclosed;

  /// No description provided for @sexNotSet.
  ///
  /// In de, this message translates to:
  /// **'nicht festgelegt'**
  String get sexNotSet;

  /// No description provided for @maxHeartRate.
  ///
  /// In de, this message translates to:
  /// **'Maximale Herzfrequenz'**
  String get maxHeartRate;

  /// No description provided for @restingHeartRate.
  ///
  /// In de, this message translates to:
  /// **'Ruheherzfrequenz'**
  String get restingHeartRate;

  /// No description provided for @signedInAs.
  ///
  /// In de, this message translates to:
  /// **'Angemeldet als {name}'**
  String signedInAs(String name);

  /// No description provided for @roleAdmin.
  ///
  /// In de, this message translates to:
  /// **'Administrator'**
  String get roleAdmin;

  /// No description provided for @noModulesTitle.
  ///
  /// In de, this message translates to:
  /// **'Noch nichts zu sehen'**
  String get noModulesTitle;

  /// No description provided for @noModulesBody.
  ///
  /// In de, this message translates to:
  /// **'Auf diesem Server ist kein Modul aktiv, das diese App kennt.'**
  String get noModulesBody;

  /// No description provided for @errorNetwork.
  ///
  /// In de, this message translates to:
  /// **'Der Server ist nicht erreichbar. Bitte Verbindung und Adresse prüfen.'**
  String get errorNetwork;

  /// No description provided for @errorInvalidCredentials.
  ///
  /// In de, this message translates to:
  /// **'E-Mail oder Passwort ist falsch.'**
  String get errorInvalidCredentials;

  /// No description provided for @errorEmailTaken.
  ///
  /// In de, this message translates to:
  /// **'Diese E-Mail-Adresse ist schon registriert.'**
  String get errorEmailTaken;

  /// No description provided for @errorRegistrationClosed.
  ///
  /// In de, this message translates to:
  /// **'Auf diesem Server können keine neuen Konten angelegt werden.'**
  String get errorRegistrationClosed;

  /// No description provided for @errorRateLimited.
  ///
  /// In de, this message translates to:
  /// **'Zu viele Versuche. Bitte kurz warten.'**
  String get errorRateLimited;

  /// No description provided for @errorValidation.
  ///
  /// In de, this message translates to:
  /// **'Die Eingaben wurden vom Server nicht angenommen.'**
  String get errorValidation;

  /// No description provided for @errorSessionExpired.
  ///
  /// In de, this message translates to:
  /// **'Die Anmeldung ist abgelaufen. Bitte neu anmelden.'**
  String get errorSessionExpired;

  /// No description provided for @errorUnknown.
  ///
  /// In de, this message translates to:
  /// **'Etwas ist schiefgegangen. Bitte später erneut versuchen.'**
  String get errorUnknown;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['de'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'de':
      return AppLocalizationsDe();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
