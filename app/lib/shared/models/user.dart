class User {
  const User({
    required this.id,
    required this.email,
    required this.displayName,
    required this.role,
    this.mfaEnabled = false,
    this.hasPassword = true,
  });

  factory User.fromJson(Map<String, dynamic> json) => User(
    id: json['id'] as String,
    email: json['email'] as String,
    displayName: json['display_name'] as String,
    role: json['role'] as String,
    mfaEnabled: json['mfa_enabled'] as bool? ?? false,
    hasPassword: json['has_password'] as bool? ?? true,
  );

  final String id;
  final String email;
  final String displayName;
  final String role;

  /// A second factor (authenticator app) is set up.
  final bool mfaEnabled;

  /// False for accounts that only sign in through single sign-on.
  final bool hasPassword;

  bool get isAdmin => role == 'admin';

  Map<String, dynamic> toJson() => {
    'id': id,
    'email': email,
    'display_name': displayName,
    'role': role,
    'mfa_enabled': mfaEnabled,
    'has_password': hasPassword,
  };
}
