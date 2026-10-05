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
  /// **'Mindestens 8 Zeichen'**
  String get passwordTooShort;

  /// No description provided for @passwordTooSimple.
  ///
  /// In de, this message translates to:
  /// **'Zu einfach: Groß- und Kleinbuchstaben, Ziffern und Sonderzeichen mischen (drei der vier Arten) – oder mindestens 20 Zeichen verwenden'**
  String get passwordTooSimple;

  /// No description provided for @passwordRules.
  ///
  /// In de, this message translates to:
  /// **'Mindestens 8 Zeichen mit drei der vier Arten Großbuchstaben, Kleinbuchstaben, Ziffern, Sonderzeichen – oder mindestens 20 Zeichen, z. B. mehrere Wörter.'**
  String get passwordRules;

  /// No description provided for @passwordRepeat.
  ///
  /// In de, this message translates to:
  /// **'Passwort wiederholen'**
  String get passwordRepeat;

  /// No description provided for @passwordsDiffer.
  ///
  /// In de, this message translates to:
  /// **'Die beiden Passwörter stimmen nicht überein'**
  String get passwordsDiffer;

  /// No description provided for @passwordChange.
  ///
  /// In de, this message translates to:
  /// **'Passwort ändern'**
  String get passwordChange;

  /// No description provided for @passwordCurrent.
  ///
  /// In de, this message translates to:
  /// **'Bisheriges Passwort'**
  String get passwordCurrent;

  /// No description provided for @passwordNew.
  ///
  /// In de, this message translates to:
  /// **'Neues Passwort'**
  String get passwordNew;

  /// No description provided for @passwordChanged.
  ///
  /// In de, this message translates to:
  /// **'Das Passwort ist geändert.'**
  String get passwordChanged;

  /// No description provided for @passwordForced.
  ///
  /// In de, this message translates to:
  /// **'Dein Passwort wurde zurückgesetzt. Bitte wähle jetzt ein neues.'**
  String get passwordForced;

  /// No description provided for @passwordSessions.
  ///
  /// In de, this message translates to:
  /// **'Andere Geräte werden dabei abgemeldet.'**
  String get passwordSessions;

  /// No description provided for @mfaTitle.
  ///
  /// In de, this message translates to:
  /// **'Zweiten Faktor einrichten'**
  String get mfaTitle;

  /// No description provided for @mfaRenew.
  ///
  /// In de, this message translates to:
  /// **'Zweiten Faktor neu einrichten'**
  String get mfaRenew;

  /// No description provided for @mfaOn.
  ///
  /// In de, this message translates to:
  /// **'Zweiter Faktor aktiv'**
  String get mfaOn;

  /// No description provided for @mfaOff.
  ///
  /// In de, this message translates to:
  /// **'Kein zweiter Faktor'**
  String get mfaOff;

  /// No description provided for @mfaForced.
  ///
  /// In de, this message translates to:
  /// **'Auf diesem Server ist ein zweiter Faktor Pflicht. Erst danach geht es weiter.'**
  String get mfaForced;

  /// No description provided for @mfaStepApp.
  ///
  /// In de, this message translates to:
  /// **'1. Eine Authenticator-App öffnen, z. B. Aegis oder FreeOTP+, und einen neuen Eintrag anlegen.'**
  String get mfaStepApp;

  /// No description provided for @mfaStepSecret.
  ///
  /// In de, this message translates to:
  /// **'2. Diesen Schlüssel in der App eintragen (zeitbasiert, 6 Ziffern):'**
  String get mfaStepSecret;

  /// No description provided for @mfaCopySecret.
  ///
  /// In de, this message translates to:
  /// **'Schlüssel kopieren'**
  String get mfaCopySecret;

  /// No description provided for @mfaCopyLink.
  ///
  /// In de, this message translates to:
  /// **'Als Link kopieren'**
  String get mfaCopyLink;

  /// No description provided for @mfaStepCode.
  ///
  /// In de, this message translates to:
  /// **'3. Den sechsstelligen Code eingeben, den die App anzeigt.'**
  String get mfaStepCode;

  /// No description provided for @mfaCode.
  ///
  /// In de, this message translates to:
  /// **'Code der Authenticator-App'**
  String get mfaCode;

  /// No description provided for @mfaCodeHint.
  ///
  /// In de, this message translates to:
  /// **'Sechs Ziffern – oder ein Wiederherstellungscode'**
  String get mfaCodeHint;

  /// No description provided for @mfaEnable.
  ///
  /// In de, this message translates to:
  /// **'Einrichten'**
  String get mfaEnable;

  /// No description provided for @mfaStepTitle.
  ///
  /// In de, this message translates to:
  /// **'Zweiter Faktor'**
  String get mfaStepTitle;

  /// No description provided for @mfaStepIntro.
  ///
  /// In de, this message translates to:
  /// **'Das Passwort stimmt. Bitte jetzt den Code aus der Authenticator-App eingeben.'**
  String get mfaStepIntro;

  /// No description provided for @mfaStepBack.
  ///
  /// In de, this message translates to:
  /// **'Mit einem anderen Konto anmelden'**
  String get mfaStepBack;

  /// No description provided for @errorMfaTokenInvalid.
  ///
  /// In de, this message translates to:
  /// **'Die Anmeldung hat zu lange gedauert. Bitte neu beginnen.'**
  String get errorMfaTokenInvalid;

  /// No description provided for @gearTypeKind.
  ///
  /// In de, this message translates to:
  /// **'Zusatzfelder'**
  String get gearTypeKind;

  /// No description provided for @gearKindNone.
  ///
  /// In de, this message translates to:
  /// **'Keine'**
  String get gearKindNone;

  /// No description provided for @gearKindBackpack.
  ///
  /// In de, this message translates to:
  /// **'Rucksack (Volumen)'**
  String get gearKindBackpack;

  /// No description provided for @gearKindShoes.
  ///
  /// In de, this message translates to:
  /// **'Schuhe (Schuhkategorie)'**
  String get gearKindShoes;

  /// No description provided for @certificatesTitle.
  ///
  /// In de, this message translates to:
  /// **'Vertraute Zertifikate'**
  String get certificatesTitle;

  /// No description provided for @certificatesIntro.
  ///
  /// In de, this message translates to:
  /// **'Diesen selbst signierten Zertifikaten vertraust du. Ohne den Eintrag fragt die App beim nächsten Verbinden erneut.'**
  String get certificatesIntro;

  /// No description provided for @certificateRemove.
  ///
  /// In de, this message translates to:
  /// **'Vertrauen entziehen'**
  String get certificateRemove;

  /// No description provided for @mfaRecoveryTitle.
  ///
  /// In de, this message translates to:
  /// **'Wiederherstellungscodes'**
  String get mfaRecoveryTitle;

  /// No description provided for @mfaRecoveryIntro.
  ///
  /// In de, this message translates to:
  /// **'Mit jedem dieser Codes kannst du dich einmal anmelden, falls die Authenticator-App nicht zur Hand ist.'**
  String get mfaRecoveryIntro;

  /// No description provided for @mfaRecoveryCopy.
  ///
  /// In de, this message translates to:
  /// **'Alle kopieren'**
  String get mfaRecoveryCopy;

  /// No description provided for @mfaRecoveryOnce.
  ///
  /// In de, this message translates to:
  /// **'Die Codes werden nur dieses eine Mal angezeigt. Bitte jetzt sicher aufbewahren.'**
  String get mfaRecoveryOnce;

  /// No description provided for @mfaRecoveryDone.
  ///
  /// In de, this message translates to:
  /// **'Ich habe die Codes gesichert'**
  String get mfaRecoveryDone;

  /// No description provided for @copied.
  ///
  /// In de, this message translates to:
  /// **'Kopiert'**
  String get copied;

  /// No description provided for @certificateTitle.
  ///
  /// In de, this message translates to:
  /// **'Unbekanntes Zertifikat'**
  String get certificateTitle;

  /// No description provided for @certificateUnknown.
  ///
  /// In de, this message translates to:
  /// **'Das Zertifikat dieses Servers stammt von keiner bekannten Stelle – etwa weil es selbst signiert ist.'**
  String get certificateUnknown;

  /// No description provided for @certificateChanged.
  ///
  /// In de, this message translates to:
  /// **'Achtung: Der Server zeigt ein anderes Zertifikat als das, dem du bisher vertraut hast.'**
  String get certificateChanged;

  /// No description provided for @certificateFingerprint.
  ///
  /// In de, this message translates to:
  /// **'Fingerabdruck (SHA-256):'**
  String get certificateFingerprint;

  /// No description provided for @certificateAdvice.
  ///
  /// In de, this message translates to:
  /// **'Vertraue ihm nur, wenn der Fingerabdruck mit dem deines Servers übereinstimmt. Die App akzeptiert danach genau dieses Zertifikat.'**
  String get certificateAdvice;

  /// No description provided for @certificateTrust.
  ///
  /// In de, this message translates to:
  /// **'Vertrauen'**
  String get certificateTrust;

  /// No description provided for @errorMfaRequired.
  ///
  /// In de, this message translates to:
  /// **'Bitte auch den Code der Authenticator-App eingeben.'**
  String get errorMfaRequired;

  /// No description provided for @errorInvalidMfaCode.
  ///
  /// In de, this message translates to:
  /// **'Der Code stimmt nicht oder wurde schon benutzt.'**
  String get errorInvalidMfaCode;

  /// No description provided for @errorWrongPassword.
  ///
  /// In de, this message translates to:
  /// **'Das bisherige Passwort stimmt nicht.'**
  String get errorWrongPassword;

  /// No description provided for @errorPasswordPersonal.
  ///
  /// In de, this message translates to:
  /// **'Das Passwort darf weder den Namen noch die E-Mail-Adresse enthalten.'**
  String get errorPasswordPersonal;

  /// No description provided for @errorPasswordCommon.
  ///
  /// In de, this message translates to:
  /// **'Dieses Passwort ist zu leicht zu erraten.'**
  String get errorPasswordCommon;

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

  /// No description provided for @delete.
  ///
  /// In de, this message translates to:
  /// **'Löschen'**
  String get delete;

  /// No description provided for @edit.
  ///
  /// In de, this message translates to:
  /// **'Bearbeiten'**
  String get edit;

  /// No description provided for @add.
  ///
  /// In de, this message translates to:
  /// **'Hinzufügen'**
  String get add;

  /// No description provided for @search.
  ///
  /// In de, this message translates to:
  /// **'Suchen'**
  String get search;

  /// No description provided for @all.
  ///
  /// In de, this message translates to:
  /// **'Alle'**
  String get all;

  /// No description provided for @none.
  ///
  /// In de, this message translates to:
  /// **'Keine'**
  String get none;

  /// No description provided for @confirmDeleteTitle.
  ///
  /// In de, this message translates to:
  /// **'Wirklich löschen?'**
  String get confirmDeleteTitle;

  /// No description provided for @close.
  ///
  /// In de, this message translates to:
  /// **'Schließen'**
  String get close;

  /// No description provided for @name.
  ///
  /// In de, this message translates to:
  /// **'Name'**
  String get name;

  /// No description provided for @offlineData.
  ///
  /// In de, this message translates to:
  /// **'Ohne Verbindung – gespeicherter Stand'**
  String get offlineData;

  /// No description provided for @errorConflict.
  ///
  /// In de, this message translates to:
  /// **'Das gibt es schon.'**
  String get errorConflict;

  /// No description provided for @errorForbidden.
  ///
  /// In de, this message translates to:
  /// **'Dafür fehlt die Berechtigung.'**
  String get errorForbidden;

  /// No description provided for @errorNotFound.
  ///
  /// In de, this message translates to:
  /// **'Nicht gefunden.'**
  String get errorNotFound;

  /// No description provided for @errorInvalidImage.
  ///
  /// In de, this message translates to:
  /// **'Die Datei ist kein unterstütztes Bild (JPEG, PNG, WebP).'**
  String get errorInvalidImage;

  /// No description provided for @errorTooLarge.
  ///
  /// In de, this message translates to:
  /// **'Die Datei ist zu groß.'**
  String get errorTooLarge;

  /// No description provided for @gearTitle.
  ///
  /// In de, this message translates to:
  /// **'Ausrüstung'**
  String get gearTitle;

  /// No description provided for @gearEmpty.
  ///
  /// In de, this message translates to:
  /// **'Noch keine Ausrüstung erfasst.'**
  String get gearEmpty;

  /// No description provided for @gearNew.
  ///
  /// In de, this message translates to:
  /// **'Neuer Gegenstand'**
  String get gearNew;

  /// No description provided for @gearEdit.
  ///
  /// In de, this message translates to:
  /// **'Gegenstand bearbeiten'**
  String get gearEdit;

  /// No description provided for @gearSearchHint.
  ///
  /// In de, this message translates to:
  /// **'Name oder Marke'**
  String get gearSearchHint;

  /// No description provided for @gearBrand.
  ///
  /// In de, this message translates to:
  /// **'Marke'**
  String get gearBrand;

  /// No description provided for @gearType.
  ///
  /// In de, this message translates to:
  /// **'Kategorie'**
  String get gearType;

  /// No description provided for @gearNoType.
  ///
  /// In de, this message translates to:
  /// **'Ohne Kategorie'**
  String get gearNoType;

  /// No description provided for @gearWeight.
  ///
  /// In de, this message translates to:
  /// **'Gewicht (g)'**
  String get gearWeight;

  /// No description provided for @gearPurchaseDate.
  ///
  /// In de, this message translates to:
  /// **'Kaufdatum'**
  String get gearPurchaseDate;

  /// No description provided for @gearPurchasePrice.
  ///
  /// In de, this message translates to:
  /// **'Kaufpreis'**
  String get gearPurchasePrice;

  /// No description provided for @gearFavorite.
  ///
  /// In de, this message translates to:
  /// **'Favorit'**
  String get gearFavorite;

  /// No description provided for @gearImageHint.
  ///
  /// In de, this message translates to:
  /// **'Erlaubt: JPEG, PNG oder WebP. Das Bild wird als JPEG gespeichert.'**
  String get gearImageHint;

  /// No description provided for @gearAttrVolume.
  ///
  /// In de, this message translates to:
  /// **'Volumen (Liter)'**
  String get gearAttrVolume;

  /// No description provided for @gearAttrShoeCategory.
  ///
  /// In de, this message translates to:
  /// **'Schuhkategorie'**
  String get gearAttrShoeCategory;

  /// No description provided for @gearShoeCategoryHint.
  ///
  /// In de, this message translates to:
  /// **'A: leichte Wanderschuhe · B: Trekking · B/C: schwere Trekkingstiefel, bedingt steigeisenfest · C: Bergstiefel · D: Expeditionsstiefel'**
  String get gearShoeCategoryHint;

  /// No description provided for @gearTagSystem.
  ///
  /// In de, this message translates to:
  /// **'Fester Tag'**
  String get gearTagSystem;

  /// No description provided for @gearPriceInvalid.
  ///
  /// In de, this message translates to:
  /// **'Betrag zwischen 0 und 1 000 000 mit höchstens zwei Nachkommastellen'**
  String get gearPriceInvalid;

  /// No description provided for @gearDescription.
  ///
  /// In de, this message translates to:
  /// **'Beschreibung'**
  String get gearDescription;

  /// No description provided for @gearNotes.
  ///
  /// In de, this message translates to:
  /// **'Notizen'**
  String get gearNotes;

  /// No description provided for @gearWebsite.
  ///
  /// In de, this message translates to:
  /// **'Website'**
  String get gearWebsite;

  /// No description provided for @gearWebsiteInvalid.
  ///
  /// In de, this message translates to:
  /// **'Adresse muss mit http:// oder https:// beginnen'**
  String get gearWebsiteInvalid;

  /// No description provided for @gearStatus.
  ///
  /// In de, this message translates to:
  /// **'Status'**
  String get gearStatus;

  /// No description provided for @gearStatusActive.
  ///
  /// In de, this message translates to:
  /// **'In Gebrauch'**
  String get gearStatusActive;

  /// No description provided for @gearStatusRetired.
  ///
  /// In de, this message translates to:
  /// **'Ausgemustert'**
  String get gearStatusRetired;

  /// No description provided for @gearSerialNumber.
  ///
  /// In de, this message translates to:
  /// **'Seriennummer'**
  String get gearSerialNumber;

  /// No description provided for @gearSize.
  ///
  /// In de, this message translates to:
  /// **'Größe'**
  String get gearSize;

  /// No description provided for @gearColor.
  ///
  /// In de, this message translates to:
  /// **'Farbe'**
  String get gearColor;

  /// No description provided for @gearTags.
  ///
  /// In de, this message translates to:
  /// **'Tags'**
  String get gearTags;

  /// No description provided for @gearImage.
  ///
  /// In de, this message translates to:
  /// **'Bild'**
  String get gearImage;

  /// No description provided for @gearImageChoose.
  ///
  /// In de, this message translates to:
  /// **'Bild wählen'**
  String get gearImageChoose;

  /// No description provided for @gearImageRemove.
  ///
  /// In de, this message translates to:
  /// **'Bild entfernen'**
  String get gearImageRemove;

  /// No description provided for @gearProposeToCatalog.
  ///
  /// In de, this message translates to:
  /// **'Im Katalog teilen'**
  String get gearProposeToCatalog;

  /// No description provided for @gearProposed.
  ///
  /// In de, this message translates to:
  /// **'Vorschlag eingereicht. Geteilt werden nur Produktdaten, keine persönlichen Angaben.'**
  String get gearProposed;

  /// No description provided for @gearAlreadyInCatalog.
  ///
  /// In de, this message translates to:
  /// **'Dieser Gegenstand ist schon mit einem Katalogeintrag verknüpft.'**
  String get gearAlreadyInCatalog;

  /// No description provided for @gearFromCatalog.
  ///
  /// In de, this message translates to:
  /// **'Aus Katalog übernehmen'**
  String get gearFromCatalog;

  /// No description provided for @gearCatalogSearchHint.
  ///
  /// In de, this message translates to:
  /// **'Katalog durchsuchen'**
  String get gearCatalogSearchHint;

  /// No description provided for @gearCatalogEmpty.
  ///
  /// In de, this message translates to:
  /// **'Nichts gefunden.'**
  String get gearCatalogEmpty;

  /// No description provided for @gearSummaryTitle.
  ///
  /// In de, this message translates to:
  /// **'Summen'**
  String get gearSummaryTitle;

  /// No description provided for @gearGroupBy.
  ///
  /// In de, this message translates to:
  /// **'Gruppieren nach'**
  String get gearGroupBy;

  /// No description provided for @gearGroupNone.
  ///
  /// In de, this message translates to:
  /// **'Gesamt'**
  String get gearGroupNone;

  /// No description provided for @gearGroupType.
  ///
  /// In de, this message translates to:
  /// **'Kategorie'**
  String get gearGroupType;

  /// No description provided for @gearGroupTag.
  ///
  /// In de, this message translates to:
  /// **'Tag'**
  String get gearGroupTag;

  /// No description provided for @gearGroupStatus.
  ///
  /// In de, this message translates to:
  /// **'Status'**
  String get gearGroupStatus;

  /// No description provided for @gearGroupBrand.
  ///
  /// In de, this message translates to:
  /// **'Marke'**
  String get gearGroupBrand;

  /// No description provided for @gearUnassigned.
  ///
  /// In de, this message translates to:
  /// **'Nicht zugeordnet'**
  String get gearUnassigned;

  /// No description provided for @gearItemCount.
  ///
  /// In de, this message translates to:
  /// **'{count, plural, =1{1 Gegenstand} other{{count} Gegenstände}}'**
  String gearItemCount(int count);

  /// No description provided for @gearTotalWeight.
  ///
  /// In de, this message translates to:
  /// **'Gesamtgewicht'**
  String get gearTotalWeight;

  /// No description provided for @gearTotalValue.
  ///
  /// In de, this message translates to:
  /// **'Kaufwert'**
  String get gearTotalValue;

  /// No description provided for @gearWithoutWeight.
  ///
  /// In de, this message translates to:
  /// **'{count} ohne Gewicht'**
  String gearWithoutWeight(int count);

  /// No description provided for @gearWithoutPrice.
  ///
  /// In de, this message translates to:
  /// **'{count} ohne Preis'**
  String gearWithoutPrice(int count);

  /// No description provided for @gearTagGroupHint.
  ///
  /// In de, this message translates to:
  /// **'Ein Gegenstand zählt in jedem seiner Tags; die Gruppen können zusammen mehr ergeben als die Gesamtsumme.'**
  String get gearTagGroupHint;

  /// No description provided for @gearListsTitle.
  ///
  /// In de, this message translates to:
  /// **'Packlisten'**
  String get gearListsTitle;

  /// No description provided for @gearListsEmpty.
  ///
  /// In de, this message translates to:
  /// **'Noch keine Packliste.'**
  String get gearListsEmpty;

  /// No description provided for @gearListNew.
  ///
  /// In de, this message translates to:
  /// **'Neue Packliste'**
  String get gearListNew;

  /// No description provided for @gearListEdit.
  ///
  /// In de, this message translates to:
  /// **'Packliste bearbeiten'**
  String get gearListEdit;

  /// No description provided for @gearQuantity.
  ///
  /// In de, this message translates to:
  /// **'Anzahl'**
  String get gearQuantity;

  /// No description provided for @gearManageTitle.
  ///
  /// In de, this message translates to:
  /// **'Tags und Kategorien'**
  String get gearManageTitle;

  /// No description provided for @gearTagNew.
  ///
  /// In de, this message translates to:
  /// **'Neuer Tag'**
  String get gearTagNew;

  /// No description provided for @gearTypeNew.
  ///
  /// In de, this message translates to:
  /// **'Neue Kategorie'**
  String get gearTypeNew;

  /// No description provided for @gearTagsEmpty.
  ///
  /// In de, this message translates to:
  /// **'Noch keine Tags. Tags sind frei wählbare Stichworte wie „Winter“ oder „Verleihbar“.'**
  String get gearTagsEmpty;

  /// No description provided for @gearStandardType.
  ///
  /// In de, this message translates to:
  /// **'Standard'**
  String get gearStandardType;

  /// No description provided for @gearOwnType.
  ///
  /// In de, this message translates to:
  /// **'Eigene'**
  String get gearOwnType;

  /// No description provided for @gearColorHex.
  ///
  /// In de, this message translates to:
  /// **'Farbe (#RRGGBB)'**
  String get gearColorHex;

  /// No description provided for @gearColorInvalid.
  ///
  /// In de, this message translates to:
  /// **'Format #RRGGBB, z. B. #3366CC'**
  String get gearColorInvalid;

  /// No description provided for @gearCatalogTitle.
  ///
  /// In de, this message translates to:
  /// **'Katalog'**
  String get gearCatalogTitle;

  /// No description provided for @gearMyProposals.
  ///
  /// In de, this message translates to:
  /// **'Meine Vorschläge'**
  String get gearMyProposals;

  /// No description provided for @gearPendingProposals.
  ///
  /// In de, this message translates to:
  /// **'Offene Vorschläge'**
  String get gearPendingProposals;

  /// No description provided for @gearNoProposals.
  ///
  /// In de, this message translates to:
  /// **'Keine Vorschläge.'**
  String get gearNoProposals;

  /// No description provided for @catalogPending.
  ///
  /// In de, this message translates to:
  /// **'Offen'**
  String get catalogPending;

  /// No description provided for @catalogApproved.
  ///
  /// In de, this message translates to:
  /// **'Freigegeben'**
  String get catalogApproved;

  /// No description provided for @catalogRejected.
  ///
  /// In de, this message translates to:
  /// **'Abgelehnt'**
  String get catalogRejected;

  /// No description provided for @catalogApprove.
  ///
  /// In de, this message translates to:
  /// **'Freigeben'**
  String get catalogApprove;

  /// No description provided for @catalogReject.
  ///
  /// In de, this message translates to:
  /// **'Ablehnen'**
  String get catalogReject;

  /// No description provided for @foodTitle.
  ///
  /// In de, this message translates to:
  /// **'Essen'**
  String get foodTitle;

  /// No description provided for @foodEmpty.
  ///
  /// In de, this message translates to:
  /// **'Noch keine eigenen Lebensmittel.'**
  String get foodEmpty;

  /// No description provided for @foodNew.
  ///
  /// In de, this message translates to:
  /// **'Neues Lebensmittel'**
  String get foodNew;

  /// No description provided for @foodEdit.
  ///
  /// In de, this message translates to:
  /// **'Lebensmittel bearbeiten'**
  String get foodEdit;

  /// No description provided for @foodSearchHint.
  ///
  /// In de, this message translates to:
  /// **'Name, Marke oder Barcode'**
  String get foodSearchHint;

  /// No description provided for @foodScan.
  ///
  /// In de, this message translates to:
  /// **'Barcode scannen'**
  String get foodScan;

  /// No description provided for @foodEnterBarcode.
  ///
  /// In de, this message translates to:
  /// **'Barcode eingeben'**
  String get foodEnterBarcode;

  /// No description provided for @foodBarcode.
  ///
  /// In de, this message translates to:
  /// **'Barcode'**
  String get foodBarcode;

  /// No description provided for @foodBarcodeInvalid.
  ///
  /// In de, this message translates to:
  /// **'8, 12, 13 oder 14 Ziffern'**
  String get foodBarcodeInvalid;

  /// No description provided for @foodBrand.
  ///
  /// In de, this message translates to:
  /// **'Marke'**
  String get foodBrand;

  /// No description provided for @foodKcal.
  ///
  /// In de, this message translates to:
  /// **'Kalorien (kcal je 100 g)'**
  String get foodKcal;

  /// No description provided for @foodKcalInvalid.
  ///
  /// In de, this message translates to:
  /// **'Zahl zwischen 0 und 900'**
  String get foodKcalInvalid;

  /// No description provided for @foodProtein.
  ///
  /// In de, this message translates to:
  /// **'Eiweiß (g)'**
  String get foodProtein;

  /// No description provided for @foodCarbs.
  ///
  /// In de, this message translates to:
  /// **'Kohlenhydrate (g)'**
  String get foodCarbs;

  /// No description provided for @foodSugar.
  ///
  /// In de, this message translates to:
  /// **'davon Zucker (g)'**
  String get foodSugar;

  /// No description provided for @foodFat.
  ///
  /// In de, this message translates to:
  /// **'Fett (g)'**
  String get foodFat;

  /// No description provided for @foodSalt.
  ///
  /// In de, this message translates to:
  /// **'Salz (g)'**
  String get foodSalt;

  /// No description provided for @foodServing.
  ///
  /// In de, this message translates to:
  /// **'Portion (g)'**
  String get foodServing;

  /// No description provided for @foodPer100gInvalid.
  ///
  /// In de, this message translates to:
  /// **'Zahl zwischen 0 und 100'**
  String get foodPer100gInvalid;

  /// No description provided for @foodSugarAboveCarbs.
  ///
  /// In de, this message translates to:
  /// **'Zucker kann nicht mehr sein als Kohlenhydrate'**
  String get foodSugarAboveCarbs;

  /// No description provided for @foodMacrosAbove100.
  ///
  /// In de, this message translates to:
  /// **'Eiweiß, Kohlenhydrate und Fett ergeben zusammen mehr als 100 g'**
  String get foodMacrosAbove100;

  /// No description provided for @foodPer100g.
  ///
  /// In de, this message translates to:
  /// **'je 100 g'**
  String get foodPer100g;

  /// No description provided for @foodKcalValue.
  ///
  /// In de, this message translates to:
  /// **'{kcal} kcal'**
  String foodKcalValue(String kcal);

  /// No description provided for @foodOwn.
  ///
  /// In de, this message translates to:
  /// **'Eigenes'**
  String get foodOwn;

  /// No description provided for @foodCatalog.
  ///
  /// In de, this message translates to:
  /// **'Katalog'**
  String get foodCatalog;

  /// No description provided for @foodSourceOff.
  ///
  /// In de, this message translates to:
  /// **'Daten: Open Food Facts (ODbL)'**
  String get foodSourceOff;

  /// No description provided for @foodNotFoundTitle.
  ///
  /// In de, this message translates to:
  /// **'Produkt nicht gefunden'**
  String get foodNotFoundTitle;

  /// No description provided for @foodNotFoundBody.
  ///
  /// In de, this message translates to:
  /// **'Zu diesem Barcode gibt es noch keinen Eintrag. Du kannst das Produkt selbst anlegen.'**
  String get foodNotFoundBody;

  /// No description provided for @foodSourceUnavailable.
  ///
  /// In de, this message translates to:
  /// **'Die Produktdatenbank ist gerade nicht erreichbar. Du kannst das Produkt selbst anlegen.'**
  String get foodSourceUnavailable;

  /// No description provided for @foodCreateOwn.
  ///
  /// In de, this message translates to:
  /// **'Selbst anlegen'**
  String get foodCreateOwn;

  /// No description provided for @foodCorrect.
  ///
  /// In de, this message translates to:
  /// **'Eigene Korrektur speichern'**
  String get foodCorrect;

  /// No description provided for @foodCorrectHint.
  ///
  /// In de, this message translates to:
  /// **'Die Änderung wird als deine eigene Kopie gespeichert; der Katalogeintrag bleibt unverändert.'**
  String get foodCorrectHint;

  /// No description provided for @foodProposeToCatalog.
  ///
  /// In de, this message translates to:
  /// **'Im Katalog teilen'**
  String get foodProposeToCatalog;

  /// No description provided for @foodProposed.
  ///
  /// In de, this message translates to:
  /// **'Vorschlag eingereicht.'**
  String get foodProposed;

  /// No description provided for @foodAlreadyInCatalog.
  ///
  /// In de, this message translates to:
  /// **'Dieses Lebensmittel ist schon mit einem Katalogeintrag verknüpft.'**
  String get foodAlreadyInCatalog;

  /// No description provided for @foodCatalogTitle.
  ///
  /// In de, this message translates to:
  /// **'Katalog'**
  String get foodCatalogTitle;

  /// No description provided for @foodScannerHint.
  ///
  /// In de, this message translates to:
  /// **'Barcode in den Rahmen halten'**
  String get foodScannerHint;

  /// No description provided for @errorBarcodeInCatalog.
  ///
  /// In de, this message translates to:
  /// **'Im Katalog gibt es schon ein Produkt mit diesem Barcode.'**
  String get errorBarcodeInCatalog;

  /// No description provided for @toursTitle.
  ///
  /// In de, this message translates to:
  /// **'Touren'**
  String get toursTitle;

  /// No description provided for @toursMine.
  ///
  /// In de, this message translates to:
  /// **'Meine'**
  String get toursMine;

  /// No description provided for @toursShared.
  ///
  /// In de, this message translates to:
  /// **'Mit mir geteilt'**
  String get toursShared;

  /// No description provided for @toursEmpty.
  ///
  /// In de, this message translates to:
  /// **'Noch keine Tour.'**
  String get toursEmpty;

  /// No description provided for @toursSharedEmpty.
  ///
  /// In de, this message translates to:
  /// **'Mit dir wurde noch keine Tour geteilt.'**
  String get toursSharedEmpty;

  /// No description provided for @tourNew.
  ///
  /// In de, this message translates to:
  /// **'Neue Tour'**
  String get tourNew;

  /// No description provided for @tourEdit.
  ///
  /// In de, this message translates to:
  /// **'Tour bearbeiten'**
  String get tourEdit;

  /// No description provided for @tourSearchHint.
  ///
  /// In de, this message translates to:
  /// **'Titel oder Fazit'**
  String get tourSearchHint;

  /// No description provided for @tourTitleField.
  ///
  /// In de, this message translates to:
  /// **'Titel'**
  String get tourTitleField;

  /// No description provided for @tourSummary.
  ///
  /// In de, this message translates to:
  /// **'Fazit'**
  String get tourSummary;

  /// No description provided for @tourSharedBy.
  ///
  /// In de, this message translates to:
  /// **'von {name}'**
  String tourSharedBy(String name);

  /// No description provided for @tourStart.
  ///
  /// In de, this message translates to:
  /// **'Start'**
  String get tourStart;

  /// No description provided for @tourEnd.
  ///
  /// In de, this message translates to:
  /// **'Ende'**
  String get tourEnd;

  /// No description provided for @tourDuration.
  ///
  /// In de, this message translates to:
  /// **'Dauer'**
  String get tourDuration;

  /// No description provided for @tourDurationMinutes.
  ///
  /// In de, this message translates to:
  /// **'Dauer (Minuten)'**
  String get tourDurationMinutes;

  /// No description provided for @tourDurationHint.
  ///
  /// In de, this message translates to:
  /// **'Leer = aus Start und Ende berechnet'**
  String get tourDurationHint;

  /// No description provided for @tourPackWeight.
  ///
  /// In de, this message translates to:
  /// **'Startgewicht'**
  String get tourPackWeight;

  /// No description provided for @tourPackWeightField.
  ///
  /// In de, this message translates to:
  /// **'Startgewicht (g)'**
  String get tourPackWeightField;

  /// No description provided for @tourPackWeightHint.
  ///
  /// In de, this message translates to:
  /// **'Leer = aus Ausrüstung und Essen berechnet'**
  String get tourPackWeightHint;

  /// No description provided for @tourCaloriesBurned.
  ///
  /// In de, this message translates to:
  /// **'Verbrauch'**
  String get tourCaloriesBurned;

  /// No description provided for @tourCaloriesBurnedField.
  ///
  /// In de, this message translates to:
  /// **'Kalorienverbrauch (kcal)'**
  String get tourCaloriesBurnedField;

  /// No description provided for @tourCaloriesBurnedHint.
  ///
  /// In de, this message translates to:
  /// **'Leer = Schätzung'**
  String get tourCaloriesBurnedHint;

  /// No description provided for @tourCaloriesEaten.
  ///
  /// In de, this message translates to:
  /// **'Gegessen'**
  String get tourCaloriesEaten;

  /// No description provided for @tourEstimated.
  ///
  /// In de, this message translates to:
  /// **'geschätzt'**
  String get tourEstimated;

  /// No description provided for @tourKcal.
  ///
  /// In de, this message translates to:
  /// **'{value} kcal'**
  String tourKcal(String value);

  /// No description provided for @tourEstimateHeartRate.
  ///
  /// In de, this message translates to:
  /// **'Schätzung aus Herzfrequenz, Gewicht und Alter (Keytel et al. 2005).'**
  String get tourEstimateHeartRate;

  /// No description provided for @tourEstimateWalking.
  ///
  /// In de, this message translates to:
  /// **'Schätzung aus Distanz, Höhenmetern, Dauer und Körper- plus Rucksackgewicht (ACSM-Gehformel). Der Abstieg zählt dabei nicht.'**
  String get tourEstimateWalking;

  /// No description provided for @tourNoEstimateProfile.
  ///
  /// In de, this message translates to:
  /// **'Für eine Schätzung fehlt das Gewicht im Profil.'**
  String get tourNoEstimateProfile;

  /// No description provided for @tourNoEstimateTrack.
  ///
  /// In de, this message translates to:
  /// **'Für eine Schätzung fehlt ein Track.'**
  String get tourNoEstimateTrack;

  /// No description provided for @tourNoEstimateDuration.
  ///
  /// In de, this message translates to:
  /// **'Für eine Schätzung fehlt die Dauer.'**
  String get tourNoEstimateDuration;

  /// No description provided for @tourOwnerOnly.
  ///
  /// In de, this message translates to:
  /// **'Zeiten und Zahlenwerte kann nur der Besitzer der Tour ändern.'**
  String get tourOwnerOnly;

  /// No description provided for @tourFacts.
  ///
  /// In de, this message translates to:
  /// **'Eckdaten'**
  String get tourFacts;

  /// No description provided for @tourTrack.
  ///
  /// In de, this message translates to:
  /// **'Track'**
  String get tourTrack;

  /// No description provided for @tourDistance.
  ///
  /// In de, this message translates to:
  /// **'Distanz'**
  String get tourDistance;

  /// No description provided for @tourAscent.
  ///
  /// In de, this message translates to:
  /// **'Aufstieg'**
  String get tourAscent;

  /// No description provided for @tourDescent.
  ///
  /// In de, this message translates to:
  /// **'Abstieg'**
  String get tourDescent;

  /// No description provided for @tourHighest.
  ///
  /// In de, this message translates to:
  /// **'Höchster Punkt'**
  String get tourHighest;

  /// No description provided for @tourMovingTime.
  ///
  /// In de, this message translates to:
  /// **'In Bewegung'**
  String get tourMovingTime;

  /// No description provided for @tourHeartRate.
  ///
  /// In de, this message translates to:
  /// **'Herzfrequenz'**
  String get tourHeartRate;

  /// No description provided for @tourHeartRateValue.
  ///
  /// In de, this message translates to:
  /// **'Ø {avg} · max. {max}'**
  String tourHeartRateValue(String avg, String max);

  /// No description provided for @tourNoTrack.
  ///
  /// In de, this message translates to:
  /// **'Noch kein Track.'**
  String get tourNoTrack;

  /// No description provided for @tourGear.
  ///
  /// In de, this message translates to:
  /// **'Ausrüstung'**
  String get tourGear;

  /// No description provided for @tourFood.
  ///
  /// In de, this message translates to:
  /// **'Essen'**
  String get tourFood;

  /// No description provided for @tourPeaks.
  ///
  /// In de, this message translates to:
  /// **'Gipfel'**
  String get tourPeaks;

  /// No description provided for @tourPartners.
  ///
  /// In de, this message translates to:
  /// **'Partner'**
  String get tourPartners;

  /// No description provided for @tourWeather.
  ///
  /// In de, this message translates to:
  /// **'Wetter'**
  String get tourWeather;

  /// No description provided for @tourPhotos.
  ///
  /// In de, this message translates to:
  /// **'Fotos'**
  String get tourPhotos;

  /// No description provided for @tourNothing.
  ///
  /// In de, this message translates to:
  /// **'Nichts eingetragen.'**
  String get tourNothing;

  /// No description provided for @tourCarried.
  ///
  /// In de, this message translates to:
  /// **'Mitgenommen'**
  String get tourCarried;

  /// No description provided for @tourEaten.
  ///
  /// In de, this message translates to:
  /// **'Gegessen'**
  String get tourEaten;

  /// No description provided for @tourAmountG.
  ///
  /// In de, this message translates to:
  /// **'Menge (g)'**
  String get tourAmountG;

  /// No description provided for @tourAddGear.
  ///
  /// In de, this message translates to:
  /// **'Ausrüstung hinzufügen'**
  String get tourAddGear;

  /// No description provided for @tourAddFood.
  ///
  /// In de, this message translates to:
  /// **'Essen hinzufügen'**
  String get tourAddFood;

  /// No description provided for @tourAddPeak.
  ///
  /// In de, this message translates to:
  /// **'Gipfel hinzufügen'**
  String get tourAddPeak;

  /// No description provided for @tourAddPartner.
  ///
  /// In de, this message translates to:
  /// **'Partner hinzufügen'**
  String get tourAddPartner;

  /// No description provided for @tourPeakName.
  ///
  /// In de, this message translates to:
  /// **'Name des Gipfels'**
  String get tourPeakName;

  /// No description provided for @tourPeakElevation.
  ///
  /// In de, this message translates to:
  /// **'Höhe (m)'**
  String get tourPeakElevation;

  /// No description provided for @tourNewContact.
  ///
  /// In de, this message translates to:
  /// **'Neuer Kontakt'**
  String get tourNewContact;

  /// No description provided for @tourWeatherOutdated.
  ///
  /// In de, this message translates to:
  /// **'Punkte oder Zeiten haben sich geändert.'**
  String get tourWeatherOutdated;

  /// No description provided for @tourWeatherRefresh.
  ///
  /// In de, this message translates to:
  /// **'Wetter neu abrufen'**
  String get tourWeatherRefresh;

  /// No description provided for @tourWeatherNone.
  ///
  /// In de, this message translates to:
  /// **'Noch kein Wetter. Dafür braucht die Tour Start oder Ende und eine Zeit.'**
  String get tourWeatherNone;

  /// No description provided for @weatherStart.
  ///
  /// In de, this message translates to:
  /// **'Start'**
  String get weatherStart;

  /// No description provided for @weatherSummit.
  ///
  /// In de, this message translates to:
  /// **'Gipfel'**
  String get weatherSummit;

  /// No description provided for @weatherEnd.
  ///
  /// In de, this message translates to:
  /// **'Ende'**
  String get weatherEnd;

  /// No description provided for @weatherManual.
  ///
  /// In de, this message translates to:
  /// **'Eigener Punkt'**
  String get weatherManual;

  /// No description provided for @weatherLine.
  ///
  /// In de, this message translates to:
  /// **'{temp} °C · Wind {wind} km/h · {clouds} % Wolken'**
  String weatherLine(String temp, String wind, String clouds);

  /// No description provided for @tourHistory.
  ///
  /// In de, this message translates to:
  /// **'Verlauf'**
  String get tourHistory;

  /// No description provided for @tourShare.
  ///
  /// In de, this message translates to:
  /// **'Teilen'**
  String get tourShare;

  /// No description provided for @tourUploadGpx.
  ///
  /// In de, this message translates to:
  /// **'GPX hochladen'**
  String get tourUploadGpx;

  /// No description provided for @tourDrawTrack.
  ///
  /// In de, this message translates to:
  /// **'Track zeichnen'**
  String get tourDrawTrack;

  /// No description provided for @tourRemoveTrack.
  ///
  /// In de, this message translates to:
  /// **'Track entfernen'**
  String get tourRemoveTrack;

  /// No description provided for @tourSetPoints.
  ///
  /// In de, this message translates to:
  /// **'Start und Ende setzen'**
  String get tourSetPoints;

  /// No description provided for @tourAddPhotos.
  ///
  /// In de, this message translates to:
  /// **'Fotos hinzufügen'**
  String get tourAddPhotos;

  /// No description provided for @tourWaypointsFromPhotos.
  ///
  /// In de, this message translates to:
  /// **'Wegpunkte aus Fotos'**
  String get tourWaypointsFromPhotos;

  /// No description provided for @tourWaypointsCreated.
  ///
  /// In de, this message translates to:
  /// **'{count, plural, =0{Keine neuen Wegpunkte} =1{1 Wegpunkt angelegt} other{{count} Wegpunkte angelegt}}'**
  String tourWaypointsCreated(int count);

  /// No description provided for @tourPhotoOffset.
  ///
  /// In de, this message translates to:
  /// **'Zeitversatz der Kamera'**
  String get tourPhotoOffset;

  /// No description provided for @tourPhotoOffsetField.
  ///
  /// In de, this message translates to:
  /// **'Versatz in Minuten'**
  String get tourPhotoOffsetField;

  /// No description provided for @tourPhotoOffsetHint.
  ///
  /// In de, this message translates to:
  /// **'Kameras speichern oft die Ortszeit ohne Zeitzone. Für Sommerzeit in Mitteleuropa: −120.'**
  String get tourPhotoOffsetHint;

  /// No description provided for @tourPhotoCaption.
  ///
  /// In de, this message translates to:
  /// **'Beschriftung'**
  String get tourPhotoCaption;

  /// No description provided for @tourPhotoCover.
  ///
  /// In de, this message translates to:
  /// **'Als Titelbild'**
  String get tourPhotoCover;

  /// No description provided for @tourPhotoIsCover.
  ///
  /// In de, this message translates to:
  /// **'Titelbild'**
  String get tourPhotoIsCover;

  /// No description provided for @tourPhotoNoPosition.
  ///
  /// In de, this message translates to:
  /// **'Ohne Position'**
  String get tourPhotoNoPosition;

  /// No description provided for @tourPhotoShowOnMap.
  ///
  /// In de, this message translates to:
  /// **'Auf Karte zeigen'**
  String get tourPhotoShowOnMap;

  /// No description provided for @tourConflictTitle.
  ///
  /// In de, this message translates to:
  /// **'Die Tour wurde inzwischen geändert'**
  String get tourConflictTitle;

  /// No description provided for @tourConflictBody.
  ///
  /// In de, this message translates to:
  /// **'Deine Änderungen wurden mit dem neuen Stand zusammengeführt. Bei diesen Feldern haben beide etwas geändert – welcher Stand soll gelten?'**
  String get tourConflictBody;

  /// No description provided for @tourConflictMine.
  ///
  /// In de, this message translates to:
  /// **'Meine Änderung'**
  String get tourConflictMine;

  /// No description provided for @tourConflictTheirs.
  ///
  /// In de, this message translates to:
  /// **'Neuer Stand'**
  String get tourConflictTheirs;

  /// No description provided for @tourConflictMerged.
  ///
  /// In de, this message translates to:
  /// **'Die Tour wurde inzwischen geändert. Deine Änderungen wurden zusammengeführt.'**
  String get tourConflictMerged;

  /// No description provided for @tourDrawHint.
  ///
  /// In de, this message translates to:
  /// **'Auf die Karte tippen, um Punkte zu setzen.'**
  String get tourDrawHint;

  /// No description provided for @tourDrawUndo.
  ///
  /// In de, this message translates to:
  /// **'Letzten Punkt entfernen'**
  String get tourDrawUndo;

  /// No description provided for @tourDrawPoints.
  ///
  /// In de, this message translates to:
  /// **'{count} Punkte'**
  String tourDrawPoints(int count);

  /// No description provided for @tourPointsHint.
  ///
  /// In de, this message translates to:
  /// **'Erst den Start, dann das Ende antippen.'**
  String get tourPointsHint;

  /// No description provided for @tourPointsFromTrack.
  ///
  /// In de, this message translates to:
  /// **'Start und Ende folgen dem Track.'**
  String get tourPointsFromTrack;

  /// No description provided for @historyCreated.
  ///
  /// In de, this message translates to:
  /// **'Angelegt'**
  String get historyCreated;

  /// No description provided for @historyUpdated.
  ///
  /// In de, this message translates to:
  /// **'Geändert'**
  String get historyUpdated;

  /// No description provided for @historyRestored.
  ///
  /// In de, this message translates to:
  /// **'Wiederhergestellt'**
  String get historyRestored;

  /// No description provided for @historyDeleted.
  ///
  /// In de, this message translates to:
  /// **'Gelöscht'**
  String get historyDeleted;

  /// No description provided for @historyRestore.
  ///
  /// In de, this message translates to:
  /// **'Diesen Stand wiederherstellen'**
  String get historyRestore;

  /// No description provided for @historyVersion.
  ///
  /// In de, this message translates to:
  /// **'Version {version}'**
  String historyVersion(int version);

  /// No description provided for @historyUnknownAuthor.
  ///
  /// In de, this message translates to:
  /// **'Entfernter Nutzer'**
  String get historyUnknownAuthor;

  /// No description provided for @historyRestoreConfirm.
  ///
  /// In de, this message translates to:
  /// **'Die Tour wird auf diesen Stand zurückgesetzt. Der Verlauf bleibt erhalten.'**
  String get historyRestoreConfirm;

  /// No description provided for @historyChanges.
  ///
  /// In de, this message translates to:
  /// **'Änderungen'**
  String get historyChanges;

  /// No description provided for @historyNoChanges.
  ///
  /// In de, this message translates to:
  /// **'Keine Änderungen an den Feldern.'**
  String get historyNoChanges;

  /// No description provided for @historyAdded.
  ///
  /// In de, this message translates to:
  /// **'hinzugefügt'**
  String get historyAdded;

  /// No description provided for @historyRemoved.
  ///
  /// In de, this message translates to:
  /// **'entfernt'**
  String get historyRemoved;

  /// No description provided for @historyChanged.
  ///
  /// In de, this message translates to:
  /// **'geändert'**
  String get historyChanged;

  /// No description provided for @shareWithUser.
  ///
  /// In de, this message translates to:
  /// **'Mit Nutzer teilen'**
  String get shareWithUser;

  /// No description provided for @shareEmailHint.
  ///
  /// In de, this message translates to:
  /// **'E-Mail-Adresse des Nutzers'**
  String get shareEmailHint;

  /// No description provided for @shareUserNotFound.
  ///
  /// In de, this message translates to:
  /// **'Kein Nutzer mit dieser E-Mail-Adresse.'**
  String get shareUserNotFound;

  /// No description provided for @shareRead.
  ///
  /// In de, this message translates to:
  /// **'Lesen'**
  String get shareRead;

  /// No description provided for @shareEditPermission.
  ///
  /// In de, this message translates to:
  /// **'Bearbeiten'**
  String get shareEditPermission;

  /// No description provided for @shareNone.
  ///
  /// In de, this message translates to:
  /// **'Mit niemandem geteilt.'**
  String get shareNone;

  /// No description provided for @sharePublicLinks.
  ///
  /// In de, this message translates to:
  /// **'Öffentliche Links'**
  String get sharePublicLinks;

  /// No description provided for @shareNewLink.
  ///
  /// In de, this message translates to:
  /// **'Neuer Link'**
  String get shareNewLink;

  /// No description provided for @shareLinkHideStart.
  ///
  /// In de, this message translates to:
  /// **'Genauen Start verbergen'**
  String get shareLinkHideStart;

  /// No description provided for @shareLinkStripGps.
  ///
  /// In de, this message translates to:
  /// **'Fotopositionen ausblenden'**
  String get shareLinkStripGps;

  /// No description provided for @shareLinkHealth.
  ///
  /// In de, this message translates to:
  /// **'Gesundheitsdaten zeigen'**
  String get shareLinkHealth;

  /// No description provided for @shareLinkRevoke.
  ///
  /// In de, this message translates to:
  /// **'Widerrufen'**
  String get shareLinkRevoke;

  /// No description provided for @shareLinkRevoked.
  ///
  /// In de, this message translates to:
  /// **'widerrufen'**
  String get shareLinkRevoked;

  /// No description provided for @shareLinkExpired.
  ///
  /// In de, this message translates to:
  /// **'abgelaufen'**
  String get shareLinkExpired;

  /// No description provided for @shareLinkCopied.
  ///
  /// In de, this message translates to:
  /// **'Link kopiert'**
  String get shareLinkCopied;

  /// No description provided for @shareLinkHint.
  ///
  /// In de, this message translates to:
  /// **'Wer den Link kennt, kann die Tour ohne Anmeldung lesen.'**
  String get shareLinkHint;

  /// No description provided for @shareNoLinks.
  ///
  /// In de, this message translates to:
  /// **'Kein öffentlicher Link.'**
  String get shareNoLinks;

  /// No description provided for @fieldTitle.
  ///
  /// In de, this message translates to:
  /// **'Titel'**
  String get fieldTitle;

  /// No description provided for @fieldSummary.
  ///
  /// In de, this message translates to:
  /// **'Fazit'**
  String get fieldSummary;

  /// No description provided for @fieldStartTime.
  ///
  /// In de, this message translates to:
  /// **'Startzeit'**
  String get fieldStartTime;

  /// No description provided for @fieldEndTime.
  ///
  /// In de, this message translates to:
  /// **'Endzeit'**
  String get fieldEndTime;

  /// No description provided for @fieldDuration.
  ///
  /// In de, this message translates to:
  /// **'Dauer'**
  String get fieldDuration;

  /// No description provided for @fieldPackWeight.
  ///
  /// In de, this message translates to:
  /// **'Startgewicht'**
  String get fieldPackWeight;

  /// No description provided for @fieldCaloriesBurned.
  ///
  /// In de, this message translates to:
  /// **'Kalorienverbrauch'**
  String get fieldCaloriesBurned;

  /// No description provided for @fieldGear.
  ///
  /// In de, this message translates to:
  /// **'Ausrüstung'**
  String get fieldGear;

  /// No description provided for @fieldFood.
  ///
  /// In de, this message translates to:
  /// **'Essen'**
  String get fieldFood;

  /// No description provided for @fieldPeaks.
  ///
  /// In de, this message translates to:
  /// **'Gipfel'**
  String get fieldPeaks;

  /// No description provided for @fieldPartners.
  ///
  /// In de, this message translates to:
  /// **'Partner'**
  String get fieldPartners;

  /// No description provided for @fieldWaypoints.
  ///
  /// In de, this message translates to:
  /// **'Wegpunkte'**
  String get fieldWaypoints;

  /// No description provided for @fieldPhotos.
  ///
  /// In de, this message translates to:
  /// **'Fotos'**
  String get fieldPhotos;

  /// No description provided for @fieldTrack.
  ///
  /// In de, this message translates to:
  /// **'Track'**
  String get fieldTrack;

  /// No description provided for @fieldOther.
  ///
  /// In de, this message translates to:
  /// **'Weiteres'**
  String get fieldOther;

  /// No description provided for @errorInvalidGpx.
  ///
  /// In de, this message translates to:
  /// **'Die Datei ist keine lesbare GPX-Datei.'**
  String get errorInvalidGpx;

  /// No description provided for @errorOwnerOnly.
  ///
  /// In de, this message translates to:
  /// **'Das kann nur der Besitzer der Tour ändern.'**
  String get errorOwnerOnly;

  /// No description provided for @errorPointsFromTrack.
  ///
  /// In de, this message translates to:
  /// **'Start und Ende folgen dem Track.'**
  String get errorPointsFromTrack;

  /// No description provided for @errorNoSamplePoints.
  ///
  /// In de, this message translates to:
  /// **'Die Tour braucht erst Start oder Ende mit einer Zeit.'**
  String get errorNoSamplePoints;

  /// No description provided for @tourRoute.
  ///
  /// In de, this message translates to:
  /// **'Wegverlauf'**
  String get tourRoute;

  /// No description provided for @stationStart.
  ///
  /// In de, this message translates to:
  /// **'Start'**
  String get stationStart;

  /// No description provided for @stationEnd.
  ///
  /// In de, this message translates to:
  /// **'Ende'**
  String get stationEnd;

  /// No description provided for @stationHighPoint.
  ///
  /// In de, this message translates to:
  /// **'Höchster Punkt'**
  String get stationHighPoint;

  /// No description provided for @stationPeak.
  ///
  /// In de, this message translates to:
  /// **'Gipfel'**
  String get stationPeak;

  /// No description provided for @stationSaddle.
  ///
  /// In de, this message translates to:
  /// **'Pass'**
  String get stationSaddle;

  /// No description provided for @stationWaypoint.
  ///
  /// In de, this message translates to:
  /// **'Wegpunkt'**
  String get stationWaypoint;

  /// No description provided for @tourDetectPlaces.
  ///
  /// In de, this message translates to:
  /// **'Gipfel und Pässe neu erkennen'**
  String get tourDetectPlaces;

  /// No description provided for @osmAttribution.
  ///
  /// In de, this message translates to:
  /// **'Namen: © OpenStreetMap-Mitwirkende (ODbL)'**
  String get osmAttribution;

  /// No description provided for @syncTitle.
  ///
  /// In de, this message translates to:
  /// **'Synchronisierung'**
  String get syncTitle;

  /// No description provided for @syncNow.
  ///
  /// In de, this message translates to:
  /// **'Jetzt synchronisieren'**
  String get syncNow;

  /// No description provided for @syncClean.
  ///
  /// In de, this message translates to:
  /// **'Alles ist mit dem Server abgeglichen.'**
  String get syncClean;

  /// No description provided for @syncWaiting.
  ///
  /// In de, this message translates to:
  /// **'{count, plural, =1{1 Änderung wartet auf eine Verbindung} other{{count} Änderungen warten auf eine Verbindung}}'**
  String syncWaiting(int count);

  /// No description provided for @syncNoConnection.
  ///
  /// In de, this message translates to:
  /// **'Der Server ist nicht erreichbar. Die Änderungen bleiben auf dem Gerät gespeichert.'**
  String get syncNoConnection;

  /// No description provided for @syncDone.
  ///
  /// In de, this message translates to:
  /// **'Synchronisiert.'**
  String get syncDone;

  /// No description provided for @syncConflict.
  ///
  /// In de, this message translates to:
  /// **'Inzwischen am Server geändert'**
  String get syncConflict;

  /// No description provided for @syncFailed.
  ///
  /// In de, this message translates to:
  /// **'Vom Server abgelehnt'**
  String get syncFailed;

  /// No description provided for @syncKeepMine.
  ///
  /// In de, this message translates to:
  /// **'Meine Änderung behalten'**
  String get syncKeepMine;

  /// No description provided for @syncTakeServer.
  ///
  /// In de, this message translates to:
  /// **'Stand des Servers übernehmen'**
  String get syncTakeServer;

  /// No description provided for @syncDiscard.
  ///
  /// In de, this message translates to:
  /// **'Verwerfen'**
  String get syncDiscard;

  /// No description provided for @syncSavedOffline.
  ///
  /// In de, this message translates to:
  /// **'Ohne Verbindung gespeichert. Wird übertragen, sobald der Server erreichbar ist.'**
  String get syncSavedOffline;

  /// No description provided for @syncLogoutWarning.
  ///
  /// In de, this message translates to:
  /// **'Es gibt Änderungen, die noch nicht übertragen wurden. Beim Abmelden gehen sie verloren.'**
  String get syncLogoutWarning;

  /// No description provided for @syncCollectionGear.
  ///
  /// In de, this message translates to:
  /// **'Ausrüstung'**
  String get syncCollectionGear;

  /// No description provided for @syncCollectionFood.
  ///
  /// In de, this message translates to:
  /// **'Lebensmittel'**
  String get syncCollectionFood;

  /// No description provided for @syncCollectionTour.
  ///
  /// In de, this message translates to:
  /// **'Tour'**
  String get syncCollectionTour;

  /// No description provided for @syncDeleted.
  ///
  /// In de, this message translates to:
  /// **'gelöscht'**
  String get syncDeleted;

  /// No description provided for @syncCollectionRoute.
  ///
  /// In de, this message translates to:
  /// **'Route'**
  String get syncCollectionRoute;

  /// No description provided for @planTitle.
  ///
  /// In de, this message translates to:
  /// **'Planung'**
  String get planTitle;

  /// No description provided for @planNew.
  ///
  /// In de, this message translates to:
  /// **'Neue Route'**
  String get planNew;

  /// No description provided for @planEmpty.
  ///
  /// In de, this message translates to:
  /// **'Noch keine geplanten Routen.'**
  String get planEmpty;

  /// No description provided for @planPending.
  ///
  /// In de, this message translates to:
  /// **'Linie wird beim nächsten Abgleich berechnet'**
  String get planPending;

  /// No description provided for @planHintStart.
  ///
  /// In de, this message translates to:
  /// **'Tippe auf die Karte, um den Start zu setzen.'**
  String get planHintStart;

  /// No description provided for @planHint.
  ///
  /// In de, this message translates to:
  /// **'Jeder Tipp auf die Karte setzt den nächsten Punkt. Ein Tipp auf einen Punkt wählt ihn zum Versetzen.'**
  String get planHint;

  /// No description provided for @planMoveHint.
  ///
  /// In de, this message translates to:
  /// **'Tippe auf die Karte, um Punkt {label} zu versetzen.'**
  String planMoveHint(String label);

  /// No description provided for @planUndo.
  ///
  /// In de, this message translates to:
  /// **'Letzten Punkt entfernen'**
  String get planUndo;

  /// No description provided for @planReverse.
  ///
  /// In de, this message translates to:
  /// **'Richtung umkehren'**
  String get planReverse;

  /// No description provided for @planClear.
  ///
  /// In de, this message translates to:
  /// **'Alle Punkte entfernen'**
  String get planClear;

  /// No description provided for @planConnection.
  ///
  /// In de, this message translates to:
  /// **'Verbindung der Punkte'**
  String get planConnection;

  /// No description provided for @planProfileHiking.
  ///
  /// In de, this message translates to:
  /// **'Den Wegen folgen'**
  String get planProfileHiking;

  /// No description provided for @planProfileDirect.
  ///
  /// In de, this message translates to:
  /// **'Luftlinie'**
  String get planProfileDirect;

  /// No description provided for @planNoRouting.
  ///
  /// In de, this message translates to:
  /// **'Auf diesem Server ist keine Wegführung eingerichtet: Die Punkte werden als Luftlinie verbunden.'**
  String get planNoRouting;

  /// No description provided for @planDifficulty.
  ///
  /// In de, this message translates to:
  /// **'Schwierigkeit bis'**
  String get planDifficulty;

  /// No description provided for @planDifficultyHint.
  ///
  /// In de, this message translates to:
  /// **'Leichtere Wege sind eingeschlossen, schwerere werden nicht benutzt.'**
  String get planDifficultyHint;

  /// No description provided for @planDifficultyLevel.
  ///
  /// In de, this message translates to:
  /// **'{level, select, 1{T1 – Wanderung} 2{T2 – Anspruchsvolle Bergwanderung} 3{T3 – Bergtour} 4{T4 – Schwere Bergtour} 5{T5 – Sehr schwere Bergtour} other{T6 – Äußerst schwierige Bergtour}}'**
  String planDifficultyLevel(String level);

  /// No description provided for @planViaFerrata.
  ///
  /// In de, this message translates to:
  /// **'Klettersteige benutzen'**
  String get planViaFerrata;

  /// No description provided for @planWaypoints.
  ///
  /// In de, this message translates to:
  /// **'Wegpunkte'**
  String get planWaypoints;

  /// No description provided for @planWaypointMenu.
  ///
  /// In de, this message translates to:
  /// **'Punkt {label}'**
  String planWaypointMenu(String label);

  /// No description provided for @planWaypointName.
  ///
  /// In de, this message translates to:
  /// **'Benennen'**
  String get planWaypointName;

  /// No description provided for @planWaypointMove.
  ///
  /// In de, this message translates to:
  /// **'Versetzen'**
  String get planWaypointMove;

  /// No description provided for @planWaypointRemove.
  ///
  /// In de, this message translates to:
  /// **'Entfernen'**
  String get planWaypointRemove;

  /// No description provided for @planDirectLeg.
  ///
  /// In de, this message translates to:
  /// **'Luftlinie hierher'**
  String get planDirectLeg;

  /// No description provided for @planDistance.
  ///
  /// In de, this message translates to:
  /// **'Strecke'**
  String get planDistance;

  /// No description provided for @planAscent.
  ///
  /// In de, this message translates to:
  /// **'Aufstieg'**
  String get planAscent;

  /// No description provided for @planDescent.
  ///
  /// In de, this message translates to:
  /// **'Abstieg'**
  String get planDescent;

  /// No description provided for @planDuration.
  ///
  /// In de, this message translates to:
  /// **'Gehzeit'**
  String get planDuration;

  /// No description provided for @planDurationNote.
  ///
  /// In de, this message translates to:
  /// **'Gehzeit geschätzt, ohne Pausen: {ascent} Hm/h auf, {descent} Hm/h ab, {distance} km/h.'**
  String planDurationNote(String ascent, String descent, String distance);

  /// No description provided for @planDifficultyField.
  ///
  /// In de, this message translates to:
  /// **'Schwierigkeit'**
  String get planDifficultyField;

  /// No description provided for @planPace.
  ///
  /// In de, this message translates to:
  /// **'Gehzeit rechnen nach'**
  String get planPace;

  /// No description provided for @planPacePreset.
  ///
  /// In de, this message translates to:
  /// **'{preset, select, dav{DAV: 300 Hm auf, 500 ab, 4 km/h} sac{SAC: 400 Hm auf, 800 ab, 4 km/h} other{Profi: 600 Hm auf, 1000 ab, 6 km/h}}'**
  String planPacePreset(String preset);

  /// No description provided for @planPaceCustom.
  ///
  /// In de, this message translates to:
  /// **'Individuell'**
  String get planPaceCustom;

  /// No description provided for @planPaceAscent.
  ///
  /// In de, this message translates to:
  /// **'Hm/h auf'**
  String get planPaceAscent;

  /// No description provided for @planPaceDescent.
  ///
  /// In de, this message translates to:
  /// **'Hm/h ab'**
  String get planPaceDescent;

  /// No description provided for @planPaceDistance.
  ///
  /// In de, this message translates to:
  /// **'km/h'**
  String get planPaceDistance;

  /// No description provided for @planPaceName.
  ///
  /// In de, this message translates to:
  /// **'Name für eigene Vorgabe'**
  String get planPaceName;

  /// No description provided for @planPaceNameMissing.
  ///
  /// In de, this message translates to:
  /// **'Bitte einen Namen und gültige Werte eingeben.'**
  String get planPaceNameMissing;

  /// No description provided for @planPaceDelete.
  ///
  /// In de, this message translates to:
  /// **'„{name}“ löschen'**
  String planPaceDelete(String name);

  /// No description provided for @planPaceNote.
  ///
  /// In de, this message translates to:
  /// **'Eigene Vorgaben siehst nur du. Pausen sind in der Gehzeit nicht enthalten.'**
  String get planPaceNote;

  /// No description provided for @planImport.
  ///
  /// In de, this message translates to:
  /// **'GPX-Datei als Route importieren'**
  String get planImport;

  /// No description provided for @planTourCreate.
  ///
  /// In de, this message translates to:
  /// **'Tour aus dieser Route anlegen'**
  String get planTourCreate;

  /// No description provided for @planTours.
  ///
  /// In de, this message translates to:
  /// **'Touren zu dieser Route'**
  String get planTours;

  /// No description provided for @planCompare.
  ///
  /// In de, this message translates to:
  /// **'Plan und Tour vergleichen'**
  String get planCompare;

  /// No description provided for @planComparePlanned.
  ///
  /// In de, this message translates to:
  /// **'Geplant'**
  String get planComparePlanned;

  /// No description provided for @planCompareActual.
  ///
  /// In de, this message translates to:
  /// **'Gegangen'**
  String get planCompareActual;

  /// No description provided for @planCompareTotal.
  ///
  /// In de, this message translates to:
  /// **'Gesamtzeit'**
  String get planCompareTotal;

  /// No description provided for @planCompareNoTrack.
  ///
  /// In de, this message translates to:
  /// **'Die Tour hat noch keinen Track.'**
  String get planCompareNoTrack;

  /// No description provided for @planCompareDeviation.
  ///
  /// In de, this message translates to:
  /// **'Der Track liegt im Mittel {mean} m neben dem Plan, höchstens {max} m; {share} % näher als 50 m.'**
  String planCompareDeviation(String mean, String max, String share);

  /// No description provided for @planTags.
  ///
  /// In de, this message translates to:
  /// **'Tags'**
  String get planTags;

  /// No description provided for @planTagsHint.
  ///
  /// In de, this message translates to:
  /// **'Durch Komma getrennt, z. B. Sommer, Gipfel'**
  String get planTagsHint;

  /// No description provided for @planStart.
  ///
  /// In de, this message translates to:
  /// **'Start (Datum und Uhrzeit)'**
  String get planStart;

  /// No description provided for @planStartHint.
  ///
  /// In de, this message translates to:
  /// **'Noch offen. Mit einem Start siehst du, wie die Sonne zur Tour steht.'**
  String get planStartHint;

  /// No description provided for @planTimeHere.
  ///
  /// In de, this message translates to:
  /// **'An dieser Stelle um {time}'**
  String planTimeHere(String time);

  /// No description provided for @planSunrise.
  ///
  /// In de, this message translates to:
  /// **'Sonnenaufgang'**
  String get planSunrise;

  /// No description provided for @planSunset.
  ///
  /// In de, this message translates to:
  /// **'Sonnenuntergang'**
  String get planSunset;

  /// No description provided for @planEnd.
  ///
  /// In de, this message translates to:
  /// **'Ende der Tour'**
  String get planEnd;

  /// No description provided for @planSummit.
  ///
  /// In de, this message translates to:
  /// **'Höchster Punkt ({elevation})'**
  String planSummit(String elevation);

  /// No description provided for @planSunAtSummit.
  ///
  /// In de, this message translates to:
  /// **'Sonne {height}° hoch im {direction}'**
  String planSunAtSummit(String height, String direction);

  /// No description provided for @compassDirection.
  ///
  /// In de, this message translates to:
  /// **'{index, select, 0{Norden} 1{Nordosten} 2{Osten} 3{Südosten} 4{Süden} 5{Südwesten} 6{Westen} other{Nordwesten}}'**
  String compassDirection(String index);

  /// No description provided for @planDaylightLeft.
  ///
  /// In de, this message translates to:
  /// **'Nach dem Ende bleiben {time} bis Sonnenuntergang.'**
  String planDaylightLeft(String time);

  /// No description provided for @planAfterSunset.
  ///
  /// In de, this message translates to:
  /// **'Die Sonne geht {time} vor dem Ende der Tour unter.'**
  String planAfterSunset(String time);

  /// No description provided for @planStartsInDark.
  ///
  /// In de, this message translates to:
  /// **'Der Start liegt vor der Morgendämmerung: Stirnlampe einplanen.'**
  String get planStartsInDark;

  /// No description provided for @planEndsInDark.
  ///
  /// In de, this message translates to:
  /// **'Das Ende liegt nach der Abenddämmerung: Stirnlampe einplanen.'**
  String get planEndsInDark;

  /// No description provided for @planRouteTitle.
  ///
  /// In de, this message translates to:
  /// **'Titel'**
  String get planRouteTitle;

  /// No description provided for @planTitleMissing.
  ///
  /// In de, this message translates to:
  /// **'Bitte einen Titel eingeben.'**
  String get planTitleMissing;

  /// No description provided for @planDescription.
  ///
  /// In de, this message translates to:
  /// **'Beschreibung'**
  String get planDescription;

  /// No description provided for @planSavedOffline.
  ///
  /// In de, this message translates to:
  /// **'Auf dem Gerät gespeichert. Die Linie wird beim nächsten Abgleich berechnet.'**
  String get planSavedOffline;

  /// No description provided for @planOffline.
  ///
  /// In de, this message translates to:
  /// **'Ohne Verbindung lässt sich die Linie nicht berechnen. Die Punkte sind vorläufig direkt verbunden.'**
  String get planOffline;

  /// No description provided for @planFailed.
  ///
  /// In de, this message translates to:
  /// **'Die Route konnte nicht berechnet werden.'**
  String get planFailed;

  /// No description provided for @errorNoRoute.
  ///
  /// In de, this message translates to:
  /// **'Zwischen diesen Punkten gibt es keinen Weg bis zur gewählten Schwierigkeit. Höhere Stufe wählen, einen Punkt versetzen oder den Abschnitt als Luftlinie planen.'**
  String get errorNoRoute;

  /// No description provided for @errorRoutingUnavailable.
  ///
  /// In de, this message translates to:
  /// **'Die Wegführung ist gerade nicht erreichbar. Luftlinien lassen sich trotzdem planen.'**
  String get errorRoutingUnavailable;

  /// No description provided for @errorVersionConflict.
  ///
  /// In de, this message translates to:
  /// **'Der Eintrag wurde inzwischen geändert. Bitte neu laden.'**
  String get errorVersionConflict;

  /// No description provided for @planGpx.
  ///
  /// In de, this message translates to:
  /// **'Als GPX speichern'**
  String get planGpx;

  /// No description provided for @planGpxSaved.
  ///
  /// In de, this message translates to:
  /// **'GPX-Datei gespeichert.'**
  String get planGpxSaved;

  /// No description provided for @planOnDevice.
  ///
  /// In de, this message translates to:
  /// **'Ohne Verbindung auf dem Gerät berechnet. Der Server rechnet beim Abgleich neu; Luftlinien bekommen erst dann ihre Höhen.'**
  String get planOnDevice;

  /// No description provided for @planOfflineNoData.
  ///
  /// In de, this message translates to:
  /// **'Für dieses Gebiet sind keine Wegdaten auf dem Gerät. Unter Planung → Offline-Daten laden oder den Abschnitt als Luftlinie planen.'**
  String get planOfflineNoData;

  /// No description provided for @offlineTitle.
  ///
  /// In de, this message translates to:
  /// **'Offline-Daten'**
  String get offlineTitle;

  /// No description provided for @offlineIntro.
  ///
  /// In de, this message translates to:
  /// **'Mit den Wegdaten eines Gebiets plant die App Routen auch ohne Verbindung. Die Daten kommen von deinem Server und stammen aus OpenStreetMap (ODbL).'**
  String get offlineIntro;

  /// No description provided for @offlineMapNote.
  ///
  /// In de, this message translates to:
  /// **'Ohne geladene Karte zeigt die App ohne Verbindung nur Ausschnitte, die du vorher schon angesehen hast.'**
  String get offlineMapNote;

  /// No description provided for @offlineNone.
  ///
  /// In de, this message translates to:
  /// **'Dieser Server bietet keine Wegdaten an.'**
  String get offlineNone;

  /// No description provided for @offlineDownload.
  ///
  /// In de, this message translates to:
  /// **'Laden'**
  String get offlineDownload;

  /// No description provided for @offlineUpdate.
  ///
  /// In de, this message translates to:
  /// **'Neu laden'**
  String get offlineUpdate;

  /// No description provided for @offlineRemove.
  ///
  /// In de, this message translates to:
  /// **'Vom Gerät entfernen'**
  String get offlineRemove;

  /// No description provided for @offlineLoaded.
  ///
  /// In de, this message translates to:
  /// **'geladen am {date}'**
  String offlineLoaded(String date);

  /// No description provided for @offlineLoading.
  ///
  /// In de, this message translates to:
  /// **'Lädt … {percent} %'**
  String offlineLoading(String percent);

  /// No description provided for @offlineEast.
  ///
  /// In de, this message translates to:
  /// **'Ost'**
  String get offlineEast;

  /// No description provided for @offlineWest.
  ///
  /// In de, this message translates to:
  /// **'West'**
  String get offlineWest;

  /// No description provided for @offlineNorth.
  ///
  /// In de, this message translates to:
  /// **'Nord'**
  String get offlineNorth;

  /// No description provided for @offlineSouth.
  ///
  /// In de, this message translates to:
  /// **'Süd'**
  String get offlineSouth;

  /// No description provided for @offlineRegionE5N45.
  ///
  /// In de, this message translates to:
  /// **'Schweiz, Vorarlberg, Süddeutschland, Nordwestitalien'**
  String get offlineRegionE5N45;

  /// No description provided for @offlineRegionE10N45.
  ///
  /// In de, this message translates to:
  /// **'Österreich West und Mitte, Bayern, Südtirol, Dolomiten'**
  String get offlineRegionE10N45;

  /// No description provided for @offlineRegionE15N45.
  ///
  /// In de, this message translates to:
  /// **'Österreich Ost, Slowenien'**
  String get offlineRegionE15N45;

  /// No description provided for @offlineRegionE5N40.
  ///
  /// In de, this message translates to:
  /// **'Seealpen, Ligurien, Korsika'**
  String get offlineRegionE5N40;

  /// No description provided for @offlineRegionE10N40.
  ///
  /// In de, this message translates to:
  /// **'Mittelitalien'**
  String get offlineRegionE10N40;

  /// No description provided for @offlineMaps.
  ///
  /// In de, this message translates to:
  /// **'Karten'**
  String get offlineMaps;

  /// No description provided for @offlineMapsIntro.
  ///
  /// In de, this message translates to:
  /// **'Eine geladene Karte zeigt die App auch ohne Verbindung. Dein Server baut sie selbst aus OpenStreetMap-Daten (ODbL).'**
  String get offlineMapsIntro;

  /// No description provided for @offlineMapsNone.
  ///
  /// In de, this message translates to:
  /// **'Dieser Server bietet keine Karten zum Herunterladen an.'**
  String get offlineMapsNone;

  /// No description provided for @offlineSegments.
  ///
  /// In de, this message translates to:
  /// **'Wegdaten für die Planung'**
  String get offlineSegments;

  /// No description provided for @mapLayers.
  ///
  /// In de, this message translates to:
  /// **'Ebenen'**
  String get mapLayers;

  /// No description provided for @mapTitle.
  ///
  /// In de, this message translates to:
  /// **'Karte'**
  String get mapTitle;

  /// No description provided for @mapBackToLogin.
  ///
  /// In de, this message translates to:
  /// **'Zur Anmeldung'**
  String get mapBackToLogin;

  /// No description provided for @mapOpenWithoutLogin.
  ///
  /// In de, this message translates to:
  /// **'Karte ohne Anmeldung ansehen'**
  String get mapOpenWithoutLogin;

  /// No description provided for @mapViaFerrata.
  ///
  /// In de, this message translates to:
  /// **'Klettersteig'**
  String get mapViaFerrata;

  /// No description provided for @mapSacScale.
  ///
  /// In de, this message translates to:
  /// **'{scale, select, hiking{T1 – Wanderung} mountain_hiking{T2 – Anspruchsvolle Bergwanderung} demanding_mountain_hiking{T3 – Bergtour} alpine_hiking{T4 – Schwere Bergtour} demanding_alpine_hiking{T5 – Sehr schwere Bergtour} difficult_alpine_hiking{T6 – Äußerst schwierige Bergtour} other{Wanderweg}}'**
  String mapSacScale(String scale);

  /// No description provided for @mapSunTimes.
  ///
  /// In de, this message translates to:
  /// **'{date}: Sonnenaufgang {rise}, Sonnenuntergang {set}'**
  String mapSunTimes(String date, String rise, String set);

  /// No description provided for @mapSunSummit.
  ///
  /// In de, this message translates to:
  /// **'Bei freiem Horizont vom Gipfel: frühestens {rise}, spätestens {set}.'**
  String mapSunSummit(String rise, String set);

  /// No description provided for @mapSunLight.
  ///
  /// In de, this message translates to:
  /// **'Hell von {dawn} bis {dusk}. Berge am Horizont sind nicht eingerechnet.'**
  String mapSunLight(String dawn, String dusk);

  /// No description provided for @mapSunNone.
  ///
  /// In de, this message translates to:
  /// **'An diesem Tag geht die Sonne hier nicht auf oder nicht unter.'**
  String get mapSunNone;

  /// No description provided for @mapLooks.
  ///
  /// In de, this message translates to:
  /// **'Darstellung'**
  String get mapLooks;

  /// No description provided for @map3dTitle.
  ///
  /// In de, this message translates to:
  /// **'3D-Ansicht'**
  String get map3dTitle;

  /// No description provided for @map3dHint.
  ///
  /// In de, this message translates to:
  /// **'Zum Ansehen: mit einem Finger verschieben, mit zwei Fingern drehen, zoomen und kippen.'**
  String get map3dHint;

  /// No description provided for @map3dUnsupported.
  ///
  /// In de, this message translates to:
  /// **'Dieses Gerät kann die 3D-Ansicht nicht darstellen.'**
  String get map3dUnsupported;

  /// No description provided for @mapSearch.
  ///
  /// In de, this message translates to:
  /// **'Ort, Gipfel oder Hütte suchen'**
  String get mapSearch;

  /// No description provided for @mapSearchNone.
  ///
  /// In de, this message translates to:
  /// **'Nichts gefunden.'**
  String get mapSearchNone;

  /// No description provided for @mapPlaceKind.
  ///
  /// In de, this message translates to:
  /// **'{kind, select, city{Stadt} town{Stadt} village{Dorf} hamlet{Weiler} peak{Gipfel} saddle{Sattel} volcano{Vulkan} hut{Hütte} lake{See} viewpoint{Aussichtspunkt} station{Bahnhof} halt{Haltestelle} parking{Parkplatz} camp_site{Campingplatz} shelter{Unterstand} attraction{Sehenswürdigkeit} castle{Burg} ruins{Ruine} cave_entrance{Höhle} waterfall{Wasserfall} spring{Quelle} other{Ort}}'**
  String mapPlaceKind(String kind);

  /// No description provided for @mapGroupTerrain.
  ///
  /// In de, this message translates to:
  /// **'Gelände'**
  String get mapGroupTerrain;

  /// No description provided for @mapGroupSnow.
  ///
  /// In de, this message translates to:
  /// **'Schnee und Lawinen'**
  String get mapGroupSnow;

  /// No description provided for @mapGroupWeather.
  ///
  /// In de, this message translates to:
  /// **'Wetter'**
  String get mapGroupWeather;

  /// No description provided for @mapOpacity.
  ///
  /// In de, this message translates to:
  /// **'Deckkraft'**
  String get mapOpacity;

  /// No description provided for @mapSlopeOpen.
  ///
  /// In de, this message translates to:
  /// **'senkrecht'**
  String get mapSlopeOpen;

  /// No description provided for @mapSlopeRange.
  ///
  /// In de, this message translates to:
  /// **'Eingefärbt von {low} bis {high}'**
  String mapSlopeRange(String low, String high);

  /// No description provided for @mapHistory.
  ///
  /// In de, this message translates to:
  /// **'Stand vom'**
  String get mapHistory;

  /// No description provided for @mapHistoryNote.
  ///
  /// In de, this message translates to:
  /// **'Heute. Lawinengefahr, Schnee und Wetter gibt es auch für einen Tag im letzten Jahr.'**
  String get mapHistoryNote;

  /// No description provided for @mapHistoryToday.
  ///
  /// In de, this message translates to:
  /// **'Heute'**
  String get mapHistoryToday;

  /// No description provided for @mapRadarRain.
  ///
  /// In de, this message translates to:
  /// **'Regenradar'**
  String get mapRadarRain;

  /// No description provided for @mapRadarClouds.
  ///
  /// In de, this message translates to:
  /// **'Wolken (Satellit)'**
  String get mapRadarClouds;

  /// No description provided for @mapRadarNote.
  ///
  /// In de, this message translates to:
  /// **'Die letzten zwei Stunden mit Zeitregler unten in der Karte.'**
  String get mapRadarNote;

  /// No description provided for @mapRadarPlay.
  ///
  /// In de, this message translates to:
  /// **'Zeitverlauf abspielen'**
  String get mapRadarPlay;

  /// No description provided for @mapBaseMap.
  ///
  /// In de, this message translates to:
  /// **'Karte'**
  String get mapBaseMap;

  /// No description provided for @mapBaseWinter.
  ///
  /// In de, this message translates to:
  /// **'Winter'**
  String get mapBaseWinter;

  /// No description provided for @mapBaseSatellite.
  ///
  /// In de, this message translates to:
  /// **'Luftbild'**
  String get mapBaseSatellite;

  /// No description provided for @mapOverlaySlope.
  ///
  /// In de, this message translates to:
  /// **'Hangneigung'**
  String get mapOverlaySlope;

  /// No description provided for @mapSlopeLegend.
  ///
  /// In de, this message translates to:
  /// **'Gelb ab 30°, orange ab 35°, rot ab 40°, violett ab 45°'**
  String get mapSlopeLegend;

  /// No description provided for @mapOverlayAvalanche.
  ///
  /// In de, this message translates to:
  /// **'Lawinengefahr'**
  String get mapOverlayAvalanche;

  /// No description provided for @mapOverlaySnow.
  ///
  /// In de, this message translates to:
  /// **'Schneebedeckung'**
  String get mapOverlaySnow;

  /// No description provided for @mapOverlayPrecipitation.
  ///
  /// In de, this message translates to:
  /// **'Niederschlag'**
  String get mapOverlayPrecipitation;

  /// No description provided for @mapAvalancheNote.
  ///
  /// In de, this message translates to:
  /// **'Höchste Gefahrenstufe des Tages je Region: 1 grün, 2 gelb, 3 orange, 4 rot, 5 schwarz. Maßgeblich ist das Bulletin des Lawinenwarndienstes.'**
  String get mapAvalancheNote;

  /// No description provided for @mapSnowNote.
  ///
  /// In de, this message translates to:
  /// **'Satellitenbild des letzten Tages; Wolken verdecken den Boden.'**
  String get mapSnowNote;

  /// No description provided for @mapPrecipitationNote.
  ///
  /// In de, this message translates to:
  /// **'Aus Satellitendaten, einige Stunden alt und grob.'**
  String get mapPrecipitationNote;

  /// No description provided for @mapPaths.
  ///
  /// In de, this message translates to:
  /// **'Wege (SAC-Skala, KS = Klettersteig):'**
  String get mapPaths;

  /// No description provided for @mapOverlayWeather0.
  ///
  /// In de, this message translates to:
  /// **'Wetter heute'**
  String get mapOverlayWeather0;

  /// No description provided for @mapOverlayWeather1.
  ///
  /// In de, this message translates to:
  /// **'Wetter morgen'**
  String get mapOverlayWeather1;

  /// No description provided for @mapOverlayWeather2.
  ///
  /// In de, this message translates to:
  /// **'Wetter übermorgen'**
  String get mapOverlayWeather2;

  /// No description provided for @mapOverlaySnowDepth.
  ///
  /// In de, this message translates to:
  /// **'Schneehöhe'**
  String get mapOverlaySnowDepth;

  /// No description provided for @mapWeatherNote.
  ///
  /// In de, this message translates to:
  /// **'Vorhersage je Ort: Wetter, höchste/tiefste Temperatur, Niederschlag oder Neuschnee. Ab mittlerer Zoomstufe.'**
  String get mapWeatherNote;

  /// No description provided for @mapSnowDepthNote.
  ///
  /// In de, this message translates to:
  /// **'Schneehöhe laut Wettermodell, keine Messung.'**
  String get mapSnowDepthNote;

  /// No description provided for @offlineMapOnly.
  ///
  /// In de, this message translates to:
  /// **'Karte (ohne Höhendaten)'**
  String get offlineMapOnly;

  /// No description provided for @offlineMapWithLayers.
  ///
  /// In de, this message translates to:
  /// **'Karte mit Schummerung, Höhenlinien und Hangneigung'**
  String get offlineMapWithLayers;
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
