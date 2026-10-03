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

  /// No description provided for @gearCurrency.
  ///
  /// In de, this message translates to:
  /// **'Währung'**
  String get gearCurrency;

  /// No description provided for @gearCurrencyRequired.
  ///
  /// In de, this message translates to:
  /// **'Zur Angabe eines Preises gehört die Währung (z. B. CHF)'**
  String get gearCurrencyRequired;

  /// No description provided for @gearCurrencyInvalid.
  ///
  /// In de, this message translates to:
  /// **'Drei Großbuchstaben, z. B. CHF'**
  String get gearCurrencyInvalid;

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

  /// No description provided for @foodScannerUnavailable.
  ///
  /// In de, this message translates to:
  /// **'Der Kamera-Scanner steht hier nicht zur Verfügung. Bitte den Barcode eintippen.'**
  String get foodScannerUnavailable;

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
