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

  @override
  String get delete => 'Löschen';

  @override
  String get edit => 'Bearbeiten';

  @override
  String get add => 'Hinzufügen';

  @override
  String get search => 'Suchen';

  @override
  String get all => 'Alle';

  @override
  String get none => 'Keine';

  @override
  String get confirmDeleteTitle => 'Wirklich löschen?';

  @override
  String get close => 'Schließen';

  @override
  String get name => 'Name';

  @override
  String get offlineData => 'Ohne Verbindung – gespeicherter Stand';

  @override
  String get errorConflict => 'Das gibt es schon.';

  @override
  String get errorForbidden => 'Dafür fehlt die Berechtigung.';

  @override
  String get errorNotFound => 'Nicht gefunden.';

  @override
  String get errorInvalidImage =>
      'Die Datei ist kein unterstütztes Bild (JPEG, PNG, WebP).';

  @override
  String get errorTooLarge => 'Die Datei ist zu groß.';

  @override
  String get gearTitle => 'Ausrüstung';

  @override
  String get gearEmpty => 'Noch keine Ausrüstung erfasst.';

  @override
  String get gearNew => 'Neuer Gegenstand';

  @override
  String get gearEdit => 'Gegenstand bearbeiten';

  @override
  String get gearSearchHint => 'Name oder Marke';

  @override
  String get gearBrand => 'Marke';

  @override
  String get gearType => 'Kategorie';

  @override
  String get gearNoType => 'Ohne Kategorie';

  @override
  String get gearWeight => 'Gewicht (g)';

  @override
  String get gearPurchaseDate => 'Kaufdatum';

  @override
  String get gearPurchasePrice => 'Kaufpreis';

  @override
  String get gearCurrency => 'Währung';

  @override
  String get gearCurrencyRequired =>
      'Zur Angabe eines Preises gehört die Währung (z. B. CHF)';

  @override
  String get gearCurrencyInvalid => 'Drei Großbuchstaben, z. B. CHF';

  @override
  String get gearPriceInvalid =>
      'Betrag zwischen 0 und 1 000 000 mit höchstens zwei Nachkommastellen';

  @override
  String get gearDescription => 'Beschreibung';

  @override
  String get gearNotes => 'Notizen';

  @override
  String get gearWebsite => 'Website';

  @override
  String get gearWebsiteInvalid =>
      'Adresse muss mit http:// oder https:// beginnen';

  @override
  String get gearStatus => 'Status';

  @override
  String get gearStatusActive => 'In Gebrauch';

  @override
  String get gearStatusRetired => 'Ausgemustert';

  @override
  String get gearSerialNumber => 'Seriennummer';

  @override
  String get gearSize => 'Größe';

  @override
  String get gearColor => 'Farbe';

  @override
  String get gearTags => 'Tags';

  @override
  String get gearImage => 'Bild';

  @override
  String get gearImageChoose => 'Bild wählen';

  @override
  String get gearImageRemove => 'Bild entfernen';

  @override
  String get gearProposeToCatalog => 'Im Katalog teilen';

  @override
  String get gearProposed =>
      'Vorschlag eingereicht. Geteilt werden nur Produktdaten, keine persönlichen Angaben.';

  @override
  String get gearAlreadyInCatalog =>
      'Dieser Gegenstand ist schon mit einem Katalogeintrag verknüpft.';

  @override
  String get gearFromCatalog => 'Aus Katalog übernehmen';

  @override
  String get gearCatalogSearchHint => 'Katalog durchsuchen';

  @override
  String get gearCatalogEmpty => 'Nichts gefunden.';

  @override
  String get gearSummaryTitle => 'Summen';

  @override
  String get gearGroupBy => 'Gruppieren nach';

  @override
  String get gearGroupNone => 'Gesamt';

  @override
  String get gearGroupType => 'Kategorie';

  @override
  String get gearGroupTag => 'Tag';

  @override
  String get gearGroupStatus => 'Status';

  @override
  String get gearGroupBrand => 'Marke';

  @override
  String get gearUnassigned => 'Nicht zugeordnet';

  @override
  String gearItemCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count Gegenstände',
      one: '1 Gegenstand',
    );
    return '$_temp0';
  }

  @override
  String get gearTotalWeight => 'Gesamtgewicht';

  @override
  String get gearTotalValue => 'Kaufwert';

  @override
  String gearWithoutWeight(int count) {
    return '$count ohne Gewicht';
  }

  @override
  String gearWithoutPrice(int count) {
    return '$count ohne Preis';
  }

  @override
  String get gearTagGroupHint =>
      'Ein Gegenstand zählt in jedem seiner Tags; die Gruppen können zusammen mehr ergeben als die Gesamtsumme.';

  @override
  String get gearListsTitle => 'Packlisten';

  @override
  String get gearListsEmpty => 'Noch keine Packliste.';

  @override
  String get gearListNew => 'Neue Packliste';

  @override
  String get gearListEdit => 'Packliste bearbeiten';

  @override
  String get gearQuantity => 'Anzahl';

  @override
  String get gearManageTitle => 'Tags und Kategorien';

  @override
  String get gearTagNew => 'Neuer Tag';

  @override
  String get gearTypeNew => 'Neue Kategorie';

  @override
  String get gearTagsEmpty =>
      'Noch keine Tags. Tags sind frei wählbare Stichworte wie „Winter“ oder „Verleihbar“.';

  @override
  String get gearStandardType => 'Standard';

  @override
  String get gearOwnType => 'Eigene';

  @override
  String get gearColorHex => 'Farbe (#RRGGBB)';

  @override
  String get gearColorInvalid => 'Format #RRGGBB, z. B. #3366CC';

  @override
  String get gearCatalogTitle => 'Katalog';

  @override
  String get gearMyProposals => 'Meine Vorschläge';

  @override
  String get gearPendingProposals => 'Offene Vorschläge';

  @override
  String get gearNoProposals => 'Keine Vorschläge.';

  @override
  String get catalogPending => 'Offen';

  @override
  String get catalogApproved => 'Freigegeben';

  @override
  String get catalogRejected => 'Abgelehnt';

  @override
  String get catalogApprove => 'Freigeben';

  @override
  String get catalogReject => 'Ablehnen';

  @override
  String get foodTitle => 'Essen';

  @override
  String get foodEmpty => 'Noch keine eigenen Lebensmittel.';

  @override
  String get foodNew => 'Neues Lebensmittel';

  @override
  String get foodEdit => 'Lebensmittel bearbeiten';

  @override
  String get foodSearchHint => 'Name, Marke oder Barcode';

  @override
  String get foodScan => 'Barcode scannen';

  @override
  String get foodEnterBarcode => 'Barcode eingeben';

  @override
  String get foodBarcode => 'Barcode';

  @override
  String get foodBarcodeInvalid => '8, 12, 13 oder 14 Ziffern';

  @override
  String get foodBrand => 'Marke';

  @override
  String get foodKcal => 'Kalorien (kcal je 100 g)';

  @override
  String get foodKcalInvalid => 'Zahl zwischen 0 und 900';

  @override
  String get foodProtein => 'Eiweiß (g)';

  @override
  String get foodCarbs => 'Kohlenhydrate (g)';

  @override
  String get foodSugar => 'davon Zucker (g)';

  @override
  String get foodFat => 'Fett (g)';

  @override
  String get foodSalt => 'Salz (g)';

  @override
  String get foodServing => 'Portion (g)';

  @override
  String get foodPer100gInvalid => 'Zahl zwischen 0 und 100';

  @override
  String get foodSugarAboveCarbs =>
      'Zucker kann nicht mehr sein als Kohlenhydrate';

  @override
  String get foodMacrosAbove100 =>
      'Eiweiß, Kohlenhydrate und Fett ergeben zusammen mehr als 100 g';

  @override
  String get foodPer100g => 'je 100 g';

  @override
  String foodKcalValue(String kcal) {
    return '$kcal kcal';
  }

  @override
  String get foodOwn => 'Eigenes';

  @override
  String get foodCatalog => 'Katalog';

  @override
  String get foodSourceOff => 'Daten: Open Food Facts (ODbL)';

  @override
  String get foodNotFoundTitle => 'Produkt nicht gefunden';

  @override
  String get foodNotFoundBody =>
      'Zu diesem Barcode gibt es noch keinen Eintrag. Du kannst das Produkt selbst anlegen.';

  @override
  String get foodSourceUnavailable =>
      'Die Produktdatenbank ist gerade nicht erreichbar. Du kannst das Produkt selbst anlegen.';

  @override
  String get foodCreateOwn => 'Selbst anlegen';

  @override
  String get foodCorrect => 'Eigene Korrektur speichern';

  @override
  String get foodCorrectHint =>
      'Die Änderung wird als deine eigene Kopie gespeichert; der Katalogeintrag bleibt unverändert.';

  @override
  String get foodProposeToCatalog => 'Im Katalog teilen';

  @override
  String get foodProposed => 'Vorschlag eingereicht.';

  @override
  String get foodAlreadyInCatalog =>
      'Dieses Lebensmittel ist schon mit einem Katalogeintrag verknüpft.';

  @override
  String get foodCatalogTitle => 'Katalog';

  @override
  String get foodScannerUnavailable =>
      'Der Kamera-Scanner steht hier nicht zur Verfügung. Bitte den Barcode eintippen.';

  @override
  String get foodScannerHint => 'Barcode in den Rahmen halten';

  @override
  String get errorBarcodeInCatalog =>
      'Im Katalog gibt es schon ein Produkt mit diesem Barcode.';
}
