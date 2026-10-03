class User {
  const User({
    required this.id,
    required this.email,
    required this.displayName,
    required this.role,
  });

  factory User.fromJson(Map<String, dynamic> json) => User(
    id: json['id'] as String,
    email: json['email'] as String,
    displayName: json['display_name'] as String,
    role: json['role'] as String,
  );

  final String id;
  final String email;
  final String displayName;
  final String role;

  bool get isAdmin => role == 'admin';

  Map<String, dynamic> toJson() => {
    'id': id,
    'email': email,
    'display_name': displayName,
    'role': role,
  };
}
