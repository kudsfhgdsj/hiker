/// Loaded data and whether it came from the device instead of the server.
class Loaded<T> {
  const Loaded(this.value, {this.offline = false});

  final T value;
  final bool offline;
}
