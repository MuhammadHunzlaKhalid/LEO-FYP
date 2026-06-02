class Session {
  Session._();
  static String _username = '';
  static String _displayName = '';
  static String get username => _username;
  static String get displayName => _displayName.isNotEmpty ? _displayName : _username;
  static void set(String u, {String name = ''}) {
    _username = u.toLowerCase().trim();
    _displayName = name;
  }
  static void clear() { _username = ''; _displayName = ''; }
  static bool get isLoggedIn => _username.isNotEmpty;
}
