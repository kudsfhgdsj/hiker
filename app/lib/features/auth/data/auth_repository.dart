import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/session/session.dart';
import '../../../shared/models/user.dart';

/// Optional data for the calorie estimate; visible to its owner only.
class Profile {
  const Profile({
    this.weightKg,
    this.birthYear,
    this.sex,
    this.maxHeartRate,
    this.restingHeartRate,
  });

  factory Profile.fromJson(Map<String, dynamic> json) => Profile(
    weightKg: (json['weight_kg'] as num?)?.toDouble(),
    birthYear: json['birth_year'] as int?,
    sex: json['sex'] as String?,
    maxHeartRate: json['max_heart_rate'] as int?,
    restingHeartRate: json['resting_heart_rate'] as int?,
  );

  static const sexValues = ['female', 'male', 'trans', 'undisclosed'];

  final double? weightKg;
  final int? birthYear;
  final String? sex;
  final int? maxHeartRate;
  final int? restingHeartRate;

  Map<String, dynamic> toJson() => {
    'weight_kg': weightKg,
    'birth_year': birthYear,
    'sex': sex,
    'max_heart_rate': maxHeartRate,
    'resting_heart_rate': restingHeartRate,
  };
}

typedef AuthResult = ({Tokens tokens, User user});

class AuthRepository {
  const AuthRepository(this._dio);

  final Dio _dio;

  AuthResult _result(Map<String, dynamic> json) => (
    tokens: Tokens(
      access: json['access_token'] as String,
      refresh: json['refresh_token'] as String,
    ),
    user: User.fromJson(json['user'] as Map<String, dynamic>),
  );

  Future<AuthResult> login({
    required String email,
    required String password,
  }) async {
    final response = await apiCall(
      () => _dio.post<Map<String, dynamic>>(
        '/auth/login',
        data: {'email': email, 'password': password},
      ),
    );
    return _result(response.data!);
  }

  Future<AuthResult> register({
    required String email,
    required String displayName,
    required String password,
  }) async {
    final response = await apiCall(
      () => _dio.post<Map<String, dynamic>>(
        '/auth/register',
        data: {
          'email': email,
          'display_name': displayName,
          'password': password,
        },
      ),
    );
    return _result(response.data!);
  }

  /// Revokes the refresh token on the server; failures are ignored because
  /// the local sign-out happens anyway.
  Future<void> logout(String refreshToken) async {
    try {
      await _dio.post<void>(
        '/auth/logout',
        data: {'refresh_token': refreshToken},
      );
    } on DioException {
      // Offline or already invalid: nothing to do.
    }
  }

  Future<Profile> fetchProfile() async {
    final response = await apiCall(
      () => _dio.get<Map<String, dynamic>>('/me/profile'),
    );
    return Profile.fromJson(response.data!);
  }

  Future<Profile> saveProfile(Profile profile) async {
    final response = await apiCall(
      () =>
          _dio.put<Map<String, dynamic>>('/me/profile', data: profile.toJson()),
    );
    return Profile.fromJson(response.data!);
  }
}

final authRepositoryProvider = Provider<AuthRepository>(
  (ref) => AuthRepository(ref.watch(dioProvider)),
);

final profileProvider = FutureProvider.autoDispose<Profile>(
  (ref) => ref.watch(authRepositoryProvider).fetchProfile(),
);
