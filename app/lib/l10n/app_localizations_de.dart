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
  String get passwordTooShort => 'Mindestens 8 Zeichen';

  @override
  String get passwordTooSimple =>
      'Zu einfach: Groß- und Kleinbuchstaben, Ziffern und Sonderzeichen mischen (drei der vier Arten) – oder mindestens 20 Zeichen verwenden';

  @override
  String get passwordRules =>
      'Mindestens 8 Zeichen mit drei der vier Arten Großbuchstaben, Kleinbuchstaben, Ziffern, Sonderzeichen – oder mindestens 20 Zeichen, z. B. mehrere Wörter.';

  @override
  String get passwordRepeat => 'Passwort wiederholen';

  @override
  String get passwordsDiffer => 'Die beiden Passwörter stimmen nicht überein';

  @override
  String get passwordChange => 'Passwort ändern';

  @override
  String get passwordCurrent => 'Bisheriges Passwort';

  @override
  String get passwordNew => 'Neues Passwort';

  @override
  String get passwordChanged => 'Das Passwort ist geändert.';

  @override
  String get passwordForced =>
      'Dein Passwort wurde zurückgesetzt. Bitte wähle jetzt ein neues.';

  @override
  String get passwordSessions => 'Andere Geräte werden dabei abgemeldet.';

  @override
  String get mfaTitle => 'Zweiten Faktor einrichten';

  @override
  String get mfaRenew => 'Zweiten Faktor neu einrichten';

  @override
  String get mfaOn => 'Zweiter Faktor aktiv';

  @override
  String get mfaOff => 'Kein zweiter Faktor';

  @override
  String get mfaForced =>
      'Auf diesem Server ist ein zweiter Faktor Pflicht. Erst danach geht es weiter.';

  @override
  String get mfaStepApp =>
      '1. Eine Authenticator-App öffnen, z. B. Aegis oder FreeOTP+, und einen neuen Eintrag anlegen.';

  @override
  String get mfaStepSecret =>
      '2. Diesen Schlüssel in der App eintragen (zeitbasiert, 6 Ziffern):';

  @override
  String get mfaCopySecret => 'Schlüssel kopieren';

  @override
  String get mfaCopyLink => 'Als Link kopieren';

  @override
  String get mfaStepCode =>
      '3. Den sechsstelligen Code eingeben, den die App anzeigt.';

  @override
  String get mfaCode => 'Code der Authenticator-App';

  @override
  String get mfaCodeHint => 'Sechs Ziffern – oder ein Wiederherstellungscode';

  @override
  String get mfaEnable => 'Einrichten';

  @override
  String get mfaStepTitle => 'Zweiter Faktor';

  @override
  String get mfaStepIntro =>
      'Das Passwort stimmt. Bitte jetzt den Code aus der Authenticator-App eingeben.';

  @override
  String get mfaStepBack => 'Mit einem anderen Konto anmelden';

  @override
  String get errorMfaTokenInvalid =>
      'Die Anmeldung hat zu lange gedauert. Bitte neu beginnen.';

  @override
  String get gearTypeKind => 'Zusatzfelder';

  @override
  String get gearKindNone => 'Keine';

  @override
  String get gearKindBackpack => 'Rucksack (Volumen)';

  @override
  String get gearKindShoes => 'Schuhe (Schuhkategorie)';

  @override
  String get certificatesTitle => 'Vertraute Zertifikate';

  @override
  String get certificatesIntro =>
      'Diesen selbst signierten Zertifikaten vertraust du. Ohne den Eintrag fragt die App beim nächsten Verbinden erneut.';

  @override
  String get certificateRemove => 'Vertrauen entziehen';

  @override
  String get mfaRecoveryTitle => 'Wiederherstellungscodes';

  @override
  String get mfaRecoveryIntro =>
      'Mit jedem dieser Codes kannst du dich einmal anmelden, falls die Authenticator-App nicht zur Hand ist.';

  @override
  String get mfaRecoveryCopy => 'Alle kopieren';

  @override
  String get mfaRecoveryOnce =>
      'Die Codes werden nur dieses eine Mal angezeigt. Bitte jetzt sicher aufbewahren.';

  @override
  String get mfaRecoveryDone => 'Ich habe die Codes gesichert';

  @override
  String get copied => 'Kopiert';

  @override
  String get certificateTitle => 'Unbekanntes Zertifikat';

  @override
  String get certificateUnknown =>
      'Das Zertifikat dieses Servers stammt von keiner bekannten Stelle – etwa weil es selbst signiert ist.';

  @override
  String get certificateChanged =>
      'Achtung: Der Server zeigt ein anderes Zertifikat als das, dem du bisher vertraut hast.';

  @override
  String get certificateFingerprint => 'Fingerabdruck (SHA-256):';

  @override
  String get certificateAdvice =>
      'Vertraue ihm nur, wenn der Fingerabdruck mit dem deines Servers übereinstimmt. Die App akzeptiert danach genau dieses Zertifikat.';

  @override
  String get certificateTrust => 'Vertrauen';

  @override
  String get errorMfaRequired =>
      'Bitte auch den Code der Authenticator-App eingeben.';

  @override
  String get errorInvalidMfaCode =>
      'Der Code stimmt nicht oder wurde schon benutzt.';

  @override
  String get errorWrongPassword => 'Das bisherige Passwort stimmt nicht.';

  @override
  String get errorPasswordPersonal =>
      'Das Passwort darf weder den Namen noch die E-Mail-Adresse enthalten.';

  @override
  String get errorPasswordCommon => 'Dieses Passwort ist zu leicht zu erraten.';

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
  String get gearFavorite => 'Favorit';

  @override
  String get gearImageHint =>
      'Erlaubt: JPEG, PNG oder WebP. Das Bild wird als JPEG gespeichert.';

  @override
  String get gearAttrVolume => 'Volumen (Liter)';

  @override
  String get gearAttrShoeCategory => 'Schuhkategorie';

  @override
  String get gearShoeCategoryHint =>
      'A: leichte Wanderschuhe · B: Trekking · B/C: schwere Trekkingstiefel, bedingt steigeisenfest · C: Bergstiefel · D: Expeditionsstiefel';

  @override
  String get gearTagSystem => 'Fester Tag';

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
  String get foodScannerHint => 'Barcode in den Rahmen halten';

  @override
  String get errorBarcodeInCatalog =>
      'Im Katalog gibt es schon ein Produkt mit diesem Barcode.';

  @override
  String get toursTitle => 'Touren';

  @override
  String get toursMine => 'Meine';

  @override
  String get toursShared => 'Mit mir geteilt';

  @override
  String get toursEmpty => 'Noch keine Tour.';

  @override
  String get toursSharedEmpty => 'Mit dir wurde noch keine Tour geteilt.';

  @override
  String get tourNew => 'Neue Tour';

  @override
  String get tourEdit => 'Tour bearbeiten';

  @override
  String get tourSearchHint => 'Titel oder Fazit';

  @override
  String get tourTitleField => 'Titel';

  @override
  String get tourSummary => 'Fazit';

  @override
  String tourSharedBy(String name) {
    return 'von $name';
  }

  @override
  String get tourStart => 'Start';

  @override
  String get tourEnd => 'Ende';

  @override
  String get tourDuration => 'Dauer';

  @override
  String get tourDurationMinutes => 'Dauer (Minuten)';

  @override
  String get tourDurationHint => 'Leer = aus Start und Ende berechnet';

  @override
  String get tourPackWeight => 'Startgewicht';

  @override
  String get tourPackWeightField => 'Startgewicht (g)';

  @override
  String get tourPackWeightHint => 'Leer = aus Ausrüstung und Essen berechnet';

  @override
  String get tourCaloriesBurned => 'Verbrauch';

  @override
  String get tourCaloriesBurnedField => 'Kalorienverbrauch (kcal)';

  @override
  String get tourCaloriesBurnedHint => 'Leer = Schätzung';

  @override
  String get tourCaloriesEaten => 'Gegessen';

  @override
  String get tourEstimated => 'geschätzt';

  @override
  String tourKcal(String value) {
    return '$value kcal';
  }

  @override
  String get tourEstimateHeartRate =>
      'Schätzung aus Herzfrequenz, Gewicht und Alter (Keytel et al. 2005).';

  @override
  String get tourEstimateWalking =>
      'Schätzung aus Distanz, Höhenmetern, Dauer und Körper- plus Rucksackgewicht (ACSM-Gehformel). Der Abstieg zählt dabei nicht.';

  @override
  String get tourNoEstimateProfile =>
      'Für eine Schätzung fehlt das Gewicht im Profil.';

  @override
  String get tourNoEstimateTrack => 'Für eine Schätzung fehlt ein Track.';

  @override
  String get tourNoEstimateDuration => 'Für eine Schätzung fehlt die Dauer.';

  @override
  String get tourOwnerOnly =>
      'Zeiten und Zahlenwerte kann nur der Besitzer der Tour ändern.';

  @override
  String get tourFacts => 'Eckdaten';

  @override
  String get tourTrack => 'Track';

  @override
  String get tourDistance => 'Distanz';

  @override
  String get tourAscent => 'Aufstieg';

  @override
  String get tourDescent => 'Abstieg';

  @override
  String get tourHighest => 'Höchster Punkt';

  @override
  String get tourMovingTime => 'In Bewegung';

  @override
  String get tourHeartRate => 'Herzfrequenz';

  @override
  String tourHeartRateValue(String avg, String max) {
    return 'Ø $avg · max. $max';
  }

  @override
  String get tourNoTrack => 'Noch kein Track.';

  @override
  String get tourGear => 'Ausrüstung';

  @override
  String get tourFood => 'Essen';

  @override
  String get tourPeaks => 'Gipfel';

  @override
  String get tourPartners => 'Partner';

  @override
  String get tourWeather => 'Wetter';

  @override
  String get tourPhotos => 'Fotos';

  @override
  String get tourNothing => 'Nichts eingetragen.';

  @override
  String get tourCarried => 'Mitgenommen';

  @override
  String get tourEaten => 'Gegessen';

  @override
  String get tourAmountG => 'Menge (g)';

  @override
  String get tourAddGear => 'Ausrüstung hinzufügen';

  @override
  String get tourAddFood => 'Essen hinzufügen';

  @override
  String get tourAddPeak => 'Gipfel hinzufügen';

  @override
  String get tourAddPartner => 'Partner hinzufügen';

  @override
  String get tourPeakName => 'Name des Gipfels';

  @override
  String get tourPeakElevation => 'Höhe (m)';

  @override
  String get tourNewContact => 'Neuer Kontakt';

  @override
  String get tourWeatherOutdated => 'Punkte oder Zeiten haben sich geändert.';

  @override
  String get tourWeatherRefresh => 'Wetter neu abrufen';

  @override
  String get tourWeatherNone =>
      'Noch kein Wetter. Dafür braucht die Tour Start oder Ende und eine Zeit.';

  @override
  String get weatherStart => 'Start';

  @override
  String get weatherSummit => 'Gipfel';

  @override
  String get weatherEnd => 'Ende';

  @override
  String get weatherManual => 'Eigener Punkt';

  @override
  String weatherLine(String temp, String wind, String clouds) {
    return '$temp °C · Wind $wind km/h · $clouds % Wolken';
  }

  @override
  String get tourHistory => 'Verlauf';

  @override
  String get tourShare => 'Teilen';

  @override
  String get tourUploadGpx => 'GPX hochladen';

  @override
  String get tourDrawTrack => 'Track zeichnen';

  @override
  String get tourRemoveTrack => 'Track entfernen';

  @override
  String get tourSetPoints => 'Start und Ende setzen';

  @override
  String get tourAddPhotos => 'Fotos hinzufügen';

  @override
  String get tourWaypointsFromPhotos => 'Wegpunkte aus Fotos';

  @override
  String tourWaypointsCreated(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count Wegpunkte angelegt',
      one: '1 Wegpunkt angelegt',
      zero: 'Keine neuen Wegpunkte',
    );
    return '$_temp0';
  }

  @override
  String get tourPhotoOffset => 'Zeitversatz der Kamera';

  @override
  String get tourPhotoOffsetField => 'Versatz in Minuten';

  @override
  String get tourPhotoOffsetHint =>
      'Kameras speichern oft die Ortszeit ohne Zeitzone. Für Sommerzeit in Mitteleuropa: −120.';

  @override
  String get tourPhotoCaption => 'Beschriftung';

  @override
  String get tourPhotoCover => 'Als Titelbild';

  @override
  String get tourPhotoIsCover => 'Titelbild';

  @override
  String get tourPhotoNoPosition => 'Ohne Position';

  @override
  String get tourPhotoShowOnMap => 'Auf Karte zeigen';

  @override
  String get tourConflictTitle => 'Die Tour wurde inzwischen geändert';

  @override
  String get tourConflictBody =>
      'Deine Änderungen wurden mit dem neuen Stand zusammengeführt. Bei diesen Feldern haben beide etwas geändert – welcher Stand soll gelten?';

  @override
  String get tourConflictMine => 'Meine Änderung';

  @override
  String get tourConflictTheirs => 'Neuer Stand';

  @override
  String get tourConflictMerged =>
      'Die Tour wurde inzwischen geändert. Deine Änderungen wurden zusammengeführt.';

  @override
  String get tourDrawHint => 'Auf die Karte tippen, um Punkte zu setzen.';

  @override
  String get tourDrawUndo => 'Letzten Punkt entfernen';

  @override
  String tourDrawPoints(int count) {
    return '$count Punkte';
  }

  @override
  String get tourPointsHint => 'Erst den Start, dann das Ende antippen.';

  @override
  String get tourPointsFromTrack => 'Start und Ende folgen dem Track.';

  @override
  String get historyCreated => 'Angelegt';

  @override
  String get historyUpdated => 'Geändert';

  @override
  String get historyRestored => 'Wiederhergestellt';

  @override
  String get historyDeleted => 'Gelöscht';

  @override
  String get historyRestore => 'Diesen Stand wiederherstellen';

  @override
  String historyVersion(int version) {
    return 'Version $version';
  }

  @override
  String get historyUnknownAuthor => 'Entfernter Nutzer';

  @override
  String get historyRestoreConfirm =>
      'Die Tour wird auf diesen Stand zurückgesetzt. Der Verlauf bleibt erhalten.';

  @override
  String get historyChanges => 'Änderungen';

  @override
  String get historyNoChanges => 'Keine Änderungen an den Feldern.';

  @override
  String get historyAdded => 'hinzugefügt';

  @override
  String get historyRemoved => 'entfernt';

  @override
  String get historyChanged => 'geändert';

  @override
  String get shareWithUser => 'Mit Nutzer teilen';

  @override
  String get shareEmailHint => 'E-Mail-Adresse des Nutzers';

  @override
  String get shareUserNotFound => 'Kein Nutzer mit dieser E-Mail-Adresse.';

  @override
  String get shareRead => 'Lesen';

  @override
  String get shareEditPermission => 'Bearbeiten';

  @override
  String get shareNone => 'Mit niemandem geteilt.';

  @override
  String get sharePublicLinks => 'Öffentliche Links';

  @override
  String get shareNewLink => 'Neuer Link';

  @override
  String get shareLinkHideStart => 'Genauen Start verbergen';

  @override
  String get shareLinkStripGps => 'Fotopositionen ausblenden';

  @override
  String get shareLinkHealth => 'Gesundheitsdaten zeigen';

  @override
  String get shareLinkRevoke => 'Widerrufen';

  @override
  String get shareLinkRevoked => 'widerrufen';

  @override
  String get shareLinkExpired => 'abgelaufen';

  @override
  String get shareLinkCopied => 'Link kopiert';

  @override
  String get shareLinkHint =>
      'Wer den Link kennt, kann die Tour ohne Anmeldung lesen.';

  @override
  String get shareNoLinks => 'Kein öffentlicher Link.';

  @override
  String get fieldTitle => 'Titel';

  @override
  String get fieldSummary => 'Fazit';

  @override
  String get fieldStartTime => 'Startzeit';

  @override
  String get fieldEndTime => 'Endzeit';

  @override
  String get fieldDuration => 'Dauer';

  @override
  String get fieldPackWeight => 'Startgewicht';

  @override
  String get fieldCaloriesBurned => 'Kalorienverbrauch';

  @override
  String get fieldGear => 'Ausrüstung';

  @override
  String get fieldFood => 'Essen';

  @override
  String get fieldPeaks => 'Gipfel';

  @override
  String get fieldPartners => 'Partner';

  @override
  String get fieldWaypoints => 'Wegpunkte';

  @override
  String get fieldPhotos => 'Fotos';

  @override
  String get fieldTrack => 'Track';

  @override
  String get fieldOther => 'Weiteres';

  @override
  String get errorInvalidGpx => 'Die Datei ist keine lesbare GPX-Datei.';

  @override
  String get errorOwnerOnly => 'Das kann nur der Besitzer der Tour ändern.';

  @override
  String get errorPointsFromTrack => 'Start und Ende folgen dem Track.';

  @override
  String get errorNoSamplePoints =>
      'Die Tour braucht erst Start oder Ende mit einer Zeit.';

  @override
  String get tourRoute => 'Wegverlauf';

  @override
  String get stationStart => 'Start';

  @override
  String get stationEnd => 'Ende';

  @override
  String get stationHighPoint => 'Höchster Punkt';

  @override
  String get stationPeak => 'Gipfel';

  @override
  String get stationSaddle => 'Pass';

  @override
  String get stationWaypoint => 'Wegpunkt';

  @override
  String get tourDetectPlaces => 'Gipfel und Pässe neu erkennen';

  @override
  String get osmAttribution => 'Namen: © OpenStreetMap-Mitwirkende (ODbL)';

  @override
  String get syncTitle => 'Synchronisierung';

  @override
  String get syncNow => 'Jetzt synchronisieren';

  @override
  String get syncClean => 'Alles ist mit dem Server abgeglichen.';

  @override
  String syncWaiting(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count Änderungen warten auf eine Verbindung',
      one: '1 Änderung wartet auf eine Verbindung',
    );
    return '$_temp0';
  }

  @override
  String get syncNoConnection =>
      'Der Server ist nicht erreichbar. Die Änderungen bleiben auf dem Gerät gespeichert.';

  @override
  String get syncDone => 'Synchronisiert.';

  @override
  String get syncConflict => 'Inzwischen am Server geändert';

  @override
  String get syncFailed => 'Vom Server abgelehnt';

  @override
  String get syncKeepMine => 'Meine Änderung behalten';

  @override
  String get syncTakeServer => 'Stand des Servers übernehmen';

  @override
  String get syncDiscard => 'Verwerfen';

  @override
  String get syncSavedOffline =>
      'Ohne Verbindung gespeichert. Wird übertragen, sobald der Server erreichbar ist.';

  @override
  String get syncLogoutWarning =>
      'Es gibt Änderungen, die noch nicht übertragen wurden. Beim Abmelden gehen sie verloren.';

  @override
  String get syncCollectionGear => 'Ausrüstung';

  @override
  String get syncCollectionFood => 'Lebensmittel';

  @override
  String get syncCollectionTour => 'Tour';

  @override
  String get syncDeleted => 'gelöscht';
}
