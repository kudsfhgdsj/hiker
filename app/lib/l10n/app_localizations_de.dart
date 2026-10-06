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
  String get tourTags => 'Tags';

  @override
  String get tourTagsHint =>
      'Durch Komma getrennt, z. B. Skitour, Hochtour, mit Kindern';

  @override
  String get toursShowMap => 'Alle Touren auf der Karte';

  @override
  String get toursShowList => 'Als Liste';

  @override
  String get toursMapEmpty =>
      'Keine Tour dieser Auswahl hat einen Track oder einen Startpunkt.';

  @override
  String get toursMapHint =>
      'Tippe auf eine Markierung, um die Tour zu öffnen.';

  @override
  String toursTagEmpty(String tag) {
    return 'Keine Tour mit dem Tag „$tag“.';
  }

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

  @override
  String get syncCollectionRoute => 'Route';

  @override
  String get planTitle => 'Planung';

  @override
  String get planNew => 'Neue Route';

  @override
  String get planEmpty => 'Noch keine geplanten Routen.';

  @override
  String get planPending => 'Linie wird beim nächsten Abgleich berechnet';

  @override
  String get planHintStart => 'Tippe auf die Karte, um den Start zu setzen.';

  @override
  String get planHint =>
      'Jeder Tipp auf die Karte setzt den nächsten Punkt. Ein Tipp auf einen Punkt wählt ihn zum Versetzen.';

  @override
  String planMoveHint(String label) {
    return 'Tippe auf die Karte, um Punkt $label zu versetzen.';
  }

  @override
  String get planUndo => 'Letzten Punkt entfernen';

  @override
  String get planReverse => 'Richtung umkehren';

  @override
  String get planClear => 'Alle Punkte entfernen';

  @override
  String get planConnection => 'Verbindung der Punkte';

  @override
  String get planProfileHiking => 'Den Wegen folgen';

  @override
  String get planProfileDirect => 'Luftlinie';

  @override
  String get planNoRouting =>
      'Auf diesem Server ist keine Wegführung eingerichtet: Die Punkte werden als Luftlinie verbunden.';

  @override
  String get planDifficulty => 'Schwierigkeit bis';

  @override
  String get planDifficultyHint =>
      'Leichtere Wege sind eingeschlossen, schwerere werden nicht benutzt.';

  @override
  String planDifficultyLevel(String level) {
    String _temp0 = intl.Intl.selectLogic(level, {
      '1': 'T1 – Wanderung',
      '2': 'T2 – Anspruchsvolle Bergwanderung',
      '3': 'T3 – Bergtour',
      '4': 'T4 – Schwere Bergtour',
      '5': 'T5 – Sehr schwere Bergtour',
      'other': 'T6 – Äußerst schwierige Bergtour',
    });
    return '$_temp0';
  }

  @override
  String get planViaFerrata => 'Klettersteige benutzen';

  @override
  String get planWaypoints => 'Wegpunkte';

  @override
  String planWaypointMenu(String label) {
    return 'Punkt $label';
  }

  @override
  String get planWaypointName => 'Benennen';

  @override
  String get planWaypointMove => 'Versetzen';

  @override
  String get planWaypointRemove => 'Entfernen';

  @override
  String get planDirectLeg => 'Luftlinie hierher';

  @override
  String get planDistance => 'Strecke';

  @override
  String get planAscent => 'Aufstieg';

  @override
  String get planDescent => 'Abstieg';

  @override
  String get planDuration => 'Gehzeit';

  @override
  String planDurationNote(String ascent, String descent, String distance) {
    return 'Gehzeit geschätzt, ohne Pausen: $ascent Hm/h auf, $descent Hm/h ab, $distance km/h.';
  }

  @override
  String get planDifficultyField => 'Schwierigkeit';

  @override
  String get planPace => 'Gehzeit rechnen nach';

  @override
  String planPacePreset(String preset) {
    String _temp0 = intl.Intl.selectLogic(preset, {
      'dav': 'DAV: 300 Hm auf, 500 ab, 4 km/h',
      'sac': 'SAC: 400 Hm auf, 800 ab, 4 km/h',
      'other': 'Profi: 600 Hm auf, 1000 ab, 6 km/h',
    });
    return '$_temp0';
  }

  @override
  String get planPaceCustom => 'Individuell';

  @override
  String get planPaceAscent => 'Hm/h auf';

  @override
  String get planPaceDescent => 'Hm/h ab';

  @override
  String get planPaceDistance => 'km/h';

  @override
  String get planPaceName => 'Name für eigene Vorgabe';

  @override
  String get planPaceNameMissing =>
      'Bitte einen Namen und gültige Werte eingeben.';

  @override
  String planPaceDelete(String name) {
    return '„$name“ löschen';
  }

  @override
  String get planPaceNote =>
      'Eigene Vorgaben siehst nur du. Pausen sind in der Gehzeit nicht enthalten.';

  @override
  String get planImport => 'GPX-Datei als Route importieren';

  @override
  String get planTourCreate => 'Tour aus dieser Route anlegen';

  @override
  String get planTours => 'Touren zu dieser Route';

  @override
  String get planCompare => 'Plan und Tour vergleichen';

  @override
  String get planComparePlanned => 'Geplant';

  @override
  String get planCompareActual => 'Gegangen';

  @override
  String get planCompareTotal => 'Gesamtzeit';

  @override
  String get planCompareOnMap => 'Auf der Karte zeigen';

  @override
  String planCompareShown(String title) {
    return 'Blau: gegangen ($title)';
  }

  @override
  String get planCompareNoTrack => 'Die Tour hat noch keinen Track.';

  @override
  String planCompareDeviation(String mean, String max, String share) {
    return 'Der Track liegt im Mittel $mean m neben dem Plan, höchstens $max m; $share % näher als 50 m.';
  }

  @override
  String get planTags => 'Tags';

  @override
  String get planTagsHint => 'Durch Komma getrennt, z. B. Sommer, Gipfel';

  @override
  String get planStart => 'Start (Datum und Uhrzeit)';

  @override
  String get planStartHint =>
      'Noch offen. Mit einem Start siehst du, wie die Sonne zur Tour steht.';

  @override
  String planTimeHere(String time) {
    return 'An dieser Stelle um $time';
  }

  @override
  String get planSunrise => 'Sonnenaufgang';

  @override
  String get planSunset => 'Sonnenuntergang';

  @override
  String get planEnd => 'Ende der Tour';

  @override
  String planSummit(String elevation) {
    return 'Höchster Punkt ($elevation)';
  }

  @override
  String planSunAtSummit(String height, String direction) {
    return 'Sonne $height° hoch im $direction';
  }

  @override
  String compassDirection(String index) {
    String _temp0 = intl.Intl.selectLogic(index, {
      '0': 'Norden',
      '1': 'Nordosten',
      '2': 'Osten',
      '3': 'Südosten',
      '4': 'Süden',
      '5': 'Südwesten',
      '6': 'Westen',
      'other': 'Nordwesten',
    });
    return '$_temp0';
  }

  @override
  String planDaylightLeft(String time) {
    return 'Nach dem Ende bleiben $time bis Sonnenuntergang.';
  }

  @override
  String planAfterSunset(String time) {
    return 'Die Sonne geht $time vor dem Ende der Tour unter.';
  }

  @override
  String get planStartsInDark =>
      'Der Start liegt vor der Morgendämmerung: Stirnlampe einplanen.';

  @override
  String get planEndsInDark =>
      'Das Ende liegt nach der Abenddämmerung: Stirnlampe einplanen.';

  @override
  String get planRouteTitle => 'Titel';

  @override
  String get planTitleMissing => 'Bitte einen Titel eingeben.';

  @override
  String get planDescription => 'Beschreibung';

  @override
  String get planSavedOffline =>
      'Auf dem Gerät gespeichert. Die Linie wird beim nächsten Abgleich berechnet.';

  @override
  String get planOffline =>
      'Ohne Verbindung lässt sich die Linie nicht berechnen. Die Punkte sind vorläufig direkt verbunden.';

  @override
  String get planFailed => 'Die Route konnte nicht berechnet werden.';

  @override
  String get errorNoRoute =>
      'Zwischen diesen Punkten gibt es keinen Weg bis zur gewählten Schwierigkeit. Höhere Stufe wählen, einen Punkt versetzen oder den Abschnitt als Luftlinie planen.';

  @override
  String get errorRoutingUnavailable =>
      'Die Wegführung ist gerade nicht erreichbar. Luftlinien lassen sich trotzdem planen.';

  @override
  String get errorVersionConflict =>
      'Der Eintrag wurde inzwischen geändert. Bitte neu laden.';

  @override
  String get planGpx => 'Als GPX speichern';

  @override
  String get planGpxSaved => 'GPX-Datei gespeichert.';

  @override
  String get planOnDevice =>
      'Ohne Verbindung auf dem Gerät berechnet. Der Server rechnet beim Abgleich neu; Luftlinien bekommen erst dann ihre Höhen.';

  @override
  String get planOfflineNoData =>
      'Für dieses Gebiet sind keine Wegdaten auf dem Gerät. Unter Planung → Offline-Daten laden oder den Abschnitt als Luftlinie planen.';

  @override
  String get offlineTitle => 'Offline-Daten';

  @override
  String get offlineIntro =>
      'Mit den Wegdaten eines Gebiets plant die App Routen auch ohne Verbindung. Die Daten kommen von deinem Server und stammen aus OpenStreetMap (ODbL).';

  @override
  String get offlineMapNote =>
      'Ohne geladene Karte zeigt die App ohne Verbindung nur Ausschnitte, die du vorher schon angesehen hast.';

  @override
  String get offlineNone => 'Dieser Server bietet keine Wegdaten an.';

  @override
  String get offlineDownload => 'Laden';

  @override
  String get offlineUpdate => 'Neu laden';

  @override
  String get offlineRemove => 'Vom Gerät entfernen';

  @override
  String offlineLoaded(String date) {
    return 'geladen am $date';
  }

  @override
  String offlineLoading(String percent) {
    return 'Lädt … $percent %';
  }

  @override
  String get offlineEast => 'Ost';

  @override
  String get offlineWest => 'West';

  @override
  String get offlineNorth => 'Nord';

  @override
  String get offlineSouth => 'Süd';

  @override
  String get offlineRegionE5N45 =>
      'Schweiz, Vorarlberg, Süddeutschland, Nordwestitalien';

  @override
  String get offlineRegionE10N45 =>
      'Österreich West und Mitte, Bayern, Südtirol, Dolomiten';

  @override
  String get offlineRegionE15N45 => 'Österreich Ost, Slowenien';

  @override
  String get offlineRegionE5N40 => 'Seealpen, Ligurien, Korsika';

  @override
  String get offlineRegionE10N40 => 'Mittelitalien';

  @override
  String get offlineMaps => 'Karten';

  @override
  String get offlineMapsIntro =>
      'Eine geladene Karte zeigt die App auch ohne Verbindung. Dein Server baut sie selbst aus OpenStreetMap-Daten (ODbL).';

  @override
  String get offlineMapsNone =>
      'Dieser Server bietet keine Karten zum Herunterladen an.';

  @override
  String get offlineSegments => 'Wegdaten für die Planung';

  @override
  String get mapLayers => 'Ebenen';

  @override
  String get mapTitle => 'Karte';

  @override
  String get mapBackToLogin => 'Zur Anmeldung';

  @override
  String get mapOpenWithoutLogin => 'Karte ohne Anmeldung ansehen';

  @override
  String get mapViaFerrata => 'Klettersteig';

  @override
  String mapSacScale(String scale) {
    String _temp0 = intl.Intl.selectLogic(scale, {
      'hiking': 'T1 – Wanderung',
      'mountain_hiking': 'T2 – Anspruchsvolle Bergwanderung',
      'demanding_mountain_hiking': 'T3 – Bergtour',
      'alpine_hiking': 'T4 – Schwere Bergtour',
      'demanding_alpine_hiking': 'T5 – Sehr schwere Bergtour',
      'difficult_alpine_hiking': 'T6 – Äußerst schwierige Bergtour',
      'other': 'Wanderweg',
    });
    return '$_temp0';
  }

  @override
  String mapSunTimes(String date, String rise, String set) {
    return '$date: Sonnenaufgang $rise, Sonnenuntergang $set';
  }

  @override
  String mapSunSummit(String rise, String set) {
    return 'Bei freiem Horizont vom Gipfel: frühestens $rise, spätestens $set.';
  }

  @override
  String mapSunLight(String dawn, String dusk) {
    return 'Hell von $dawn bis $dusk. Berge am Horizont sind nicht eingerechnet.';
  }

  @override
  String get mapSunNone =>
      'An diesem Tag geht die Sonne hier nicht auf oder nicht unter.';

  @override
  String get mapLooks => 'Darstellung';

  @override
  String get statsTitle => 'Statistik';

  @override
  String get statsHint => 'Strecke, Höhenmeter, Gipfel und wo du warst';

  @override
  String get statsTotals => 'Alle Touren zusammen';

  @override
  String get statsTours => 'Touren';

  @override
  String get statsDays => 'Tage unterwegs';

  @override
  String get statsMovingTime => 'Zeit in Bewegung';

  @override
  String get statsPeaks => 'Gipfel';

  @override
  String statsWithoutTrack(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count Touren haben',
      one: '1 Tour hat',
    );
    return '$_temp0 keinen Track und zählen nicht bei Strecke und Höhenmetern.';
  }

  @override
  String statsYearLine(int tours, int days) {
    String _temp0 = intl.Intl.pluralLogic(
      tours,
      locale: localeName,
      other: '$tours Touren',
      one: '1 Tour',
    );
    String _temp1 = intl.Intl.pluralLogic(
      days,
      locale: localeName,
      other: '$days Tage',
      one: '1 Tag',
    );
    return '$_temp0, $_temp1';
  }

  @override
  String statsCalendar(String year) {
    return 'Tage unterwegs $year';
  }

  @override
  String get statsCalendarNote =>
      'Farbe nach Höhenmetern im Aufstieg. Ein Tipp auf einen Tag öffnet die Tour.';

  @override
  String get statsMap => 'Wo ich war';

  @override
  String get statsMapNote =>
      'Alle eigenen Tracks. Oft begangene Strecken erscheinen dunkler.';

  @override
  String get statsNoTracks => 'Noch keine Tracks.';

  @override
  String statsClimbed(int count) {
    return 'Bestiegene Gipfel ($count)';
  }

  @override
  String get statsNoPeaks =>
      'Noch keine Gipfel. Sie kommen aus den Gipfeln deiner Touren.';

  @override
  String statsVisits(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count Besuche',
      one: '1 Besuch',
    );
    return '$_temp0';
  }

  @override
  String get statsWishes => 'Wunschgipfel';

  @override
  String get statsNoWishes => 'Noch keine Wunschgipfel.';

  @override
  String get statsWishNew => 'Wunschgipfel hinzufügen';

  @override
  String get statsWishDone => 'bestiegen';

  @override
  String get statsPeak => 'Gipfel';

  @override
  String get statsElevation => 'Höhe (m)';

  @override
  String get statsNote => 'Notiz';

  @override
  String get mapKey => 'Legende';

  @override
  String mapKeySection(String section) {
    String _temp0 = intl.Intl.selectLogic(section, {
      'paths': 'Wege',
      'signs': 'Zeichen',
      'lines': 'Linien',
      'areas': 'Flächen',
      'other': 'Weiteres',
    });
    return '$_temp0';
  }

  @override
  String mapKeyItem(String item) {
    String _temp0 = intl.Intl.selectLogic(item, {
      'grade_easy': 'Wanderweg bis Bergtour (T1–T4)',
      'grade_t5': 'Sehr schwere Bergtour (T5)',
      'grade_t6': 'Äußerst schwierig (T6)',
      'path': 'Weg',
      'path_marked': 'Bergweg mit Schwierigkeitsangabe',
      'via_ferrata': 'Klettersteig',
      'peak': 'Gipfel',
      'saddle': 'Sattel, Pass',
      'hut': 'Hütte',
      'shelter': 'Unterstand',
      'viewpoint': 'Aussichtspunkt',
      'parking': 'Parkplatz',
      'cable_car': 'Seilbahnstation',
      'ladder': 'Leiter',
      'track': 'Forst- oder Feldweg',
      'road': 'Straße',
      'rail': 'Bahn',
      'aerialway': 'Seilbahn, Lift',
      'boundary': 'Grenze',
      'contour': 'Höhenlinie',
      'wood': 'Wald',
      'grass': 'Wiese',
      'rock': 'Fels, Geröll',
      'ice': 'Gletscher',
      'water': 'Gewässer',
      'other': 'Sonstiges',
    });
    return '$_temp0';
  }

  @override
  String mapKeyFrom(String angle) {
    return 'ab $angle°';
  }

  @override
  String mapKeyLevel(String level) {
    return 'Stufe $level';
  }

  @override
  String get map3dTitle => '3D-Ansicht';

  @override
  String get map3dHint =>
      'Zum Ansehen: mit einem Finger verschieben, mit zwei Fingern drehen, zoomen und kippen.';

  @override
  String get map3dUnsupported =>
      'Dieses Gerät kann die 3D-Ansicht nicht darstellen.';

  @override
  String get mapSearch => 'Ort, Gipfel oder Hütte suchen';

  @override
  String get mapSearchNone => 'Nichts gefunden.';

  @override
  String mapPlaceKind(String kind) {
    String _temp0 = intl.Intl.selectLogic(kind, {
      'city': 'Stadt',
      'town': 'Stadt',
      'village': 'Dorf',
      'hamlet': 'Weiler',
      'peak': 'Gipfel',
      'saddle': 'Sattel',
      'volcano': 'Vulkan',
      'hut': 'Hütte',
      'lake': 'See',
      'viewpoint': 'Aussichtspunkt',
      'station': 'Bahnhof',
      'halt': 'Haltestelle',
      'parking': 'Parkplatz',
      'camp_site': 'Campingplatz',
      'shelter': 'Unterstand',
      'attraction': 'Sehenswürdigkeit',
      'castle': 'Burg',
      'ruins': 'Ruine',
      'cave_entrance': 'Höhle',
      'waterfall': 'Wasserfall',
      'spring': 'Quelle',
      'other': 'Ort',
    });
    return '$_temp0';
  }

  @override
  String get mapGroupTerrain => 'Gelände';

  @override
  String get mapGroupSnow => 'Schnee und Lawinen';

  @override
  String get mapGroupWeather => 'Wetter';

  @override
  String get mapOpacity => 'Deckkraft';

  @override
  String get mapSlopeOpen => 'senkrecht';

  @override
  String mapSlopeRange(String low, String high) {
    return 'Eingefärbt von $low bis $high';
  }

  @override
  String get mapHistory => 'Stand vom';

  @override
  String get mapHistoryNote =>
      'Heute. Lawinengefahr, Schnee und Wetter gibt es auch für einen Tag im letzten Jahr.';

  @override
  String get mapHistoryToday => 'Heute';

  @override
  String get mapRadarRain => 'Regenradar';

  @override
  String get mapRadarClouds => 'Wolken (Satellit)';

  @override
  String get mapRadarNote =>
      'Die letzten zwei Stunden mit Zeitregler unten in der Karte.';

  @override
  String get mapRadarPlay => 'Zeitverlauf abspielen';

  @override
  String get mapBaseMap => 'Standard';

  @override
  String get mapBaseWinter => 'Winter';

  @override
  String get mapBaseTopo => 'Topo';

  @override
  String get mapBaseAlpenverein => 'Alpenverein';

  @override
  String get mapBaseOutdooractive => 'Outdooractive';

  @override
  String get mapBaseKompass => 'Kompass';

  @override
  String get mapBaseNote =>
      'Alle Darstellungen sind selbst aus OpenStreetMap-Daten gezeichnet. „Alpenverein“, „Outdooractive“ und „Kompass“ sind an die Karten dieser Anbieter angelehnt und stammen nicht von ihnen.';

  @override
  String get mapBaseSatellite => 'Luftbild';

  @override
  String get mapOverlaySlope => 'Hangneigung';

  @override
  String get mapSlopeLegend =>
      'Gelb ab 30°, orange ab 35°, rot ab 40°, violett ab 45°';

  @override
  String get mapOverlayAvalanche => 'Lawinengefahr';

  @override
  String get mapOverlaySnow => 'Schneebedeckung';

  @override
  String get mapOverlayPrecipitation => 'Niederschlag';

  @override
  String get mapAvalancheNote =>
      'Höchste Gefahrenstufe des Tages je Region: 1 grün, 2 gelb, 3 orange, 4 rot, 5 schwarz. Maßgeblich ist das Bulletin des Lawinenwarndienstes.';

  @override
  String get mapSnowNote =>
      'Satellitenbild des letzten Tages; Wolken verdecken den Boden.';

  @override
  String get mapPrecipitationNote =>
      'Aus Satellitendaten, einige Stunden alt und grob.';

  @override
  String get mapPaths =>
      'Wege (SAC-Skala; KS = Klettersteig, mit Querstrichen und Leiter):';

  @override
  String get mapOverlayWeather0 => 'Wetter heute';

  @override
  String get mapOverlayWeather1 => 'Wetter morgen';

  @override
  String get mapOverlayWeather2 => 'Wetter übermorgen';

  @override
  String get mapOverlaySnowDepth => 'Schneehöhe';

  @override
  String get mapWeatherNote =>
      'Vorhersage je Ort: Wetter, höchste/tiefste Temperatur, Niederschlag oder Neuschnee. Ab mittlerer Zoomstufe.';

  @override
  String get mapSnowDepthNote => 'Schneehöhe laut Wettermodell, keine Messung.';

  @override
  String get offlineMapOnly => 'Karte (ohne Höhendaten)';

  @override
  String get offlineMapWithLayers =>
      'Karte mit Schummerung, Höhenlinien und Hangneigung';

  @override
  String get offlineDetailTitle => 'Wie fein ohne Netz?';

  @override
  String offlineDetailLoaded(String level) {
    return 'Höhendaten ohne Netz: $level';
  }

  @override
  String get offlineDetailBase => 'Grob';

  @override
  String get offlineDetailSmall => 'Klein';

  @override
  String get offlineDetailMedium => 'Mittel';

  @override
  String get offlineDetailFull => 'Voll';

  @override
  String get offlineDetailBaseNote =>
      'Höhen mit rund 50 m je Bildpunkt, Höhenlinien alle 50 m. Reicht für die Schummerung.';

  @override
  String get offlineDetailSmallNote =>
      'Höhen mit rund 25 m je Bildpunkt, Höhenlinien alle 20 m, Hangneigung feiner.';

  @override
  String get offlineDetailMediumNote =>
      'Höhen mit rund 13 m je Bildpunkt. Schummerung und 3D fast so scharf wie mit Netz.';

  @override
  String get offlineDetailFullNote =>
      'Höhen mit rund 6,5 m je Bildpunkt – dasselbe wie mit Netz.';
}
