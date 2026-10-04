# Eingebundene Bibliotheken

`brouter-1.7.10-ro.jar` ist der Routing-Kern von BRouter (https://github.com/abrensch/brouter,
MIT-Lizenz), unverändert aus `brouter-1.7.10.zip` der Veröffentlichung v1.7.10
(SHA-256 des Archivs: `023fec3ba997758e8cd7ab9e1bae52e962af3f00b57683e3de86b84ffad01532`,
SHA-256 dieser Datei: `598b647f2384a22a43495de7aee44f31e037062ec9c317e3bcc58cf799dbd972`).
Die App berechnet damit Routen ohne Netz (`MainActivity.kt`, Kanal `hiker/routing`).

Beim Aktualisieren gehören dieselbe Version in `deploy/brouter/Dockerfile` und die dazu
passende `lookups.dat` nach `app/assets/brouter/`.
