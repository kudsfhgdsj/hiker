import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../shared/models/user.dart';
import '../config/app_config.dart';
import '../storage/key_value_store.dart';

class Tokens {
  const Tokens({required this.access, required this.refresh});

  final String access;
  final String refresh;
}

enum SessionStatus { unknown, signedOut, signedIn }

class SessionState {
  const SessionState({
    this.status = SessionStatus.unknown,
    this.baseUrl = '',
    this.user,
    this.tokens,
  });

  final SessionStatus status;

  /// Server address without trailing slash; empty until one is known.
  final String baseUrl;
  final User? user;
  final Tokens? tokens;

  bool get isSignedIn => status == SessionStatus.signedIn;
}

/// Who is signed in and against which server. Persisted on the device, so
/// that the app also opens without network.
class SessionController extends Notifier<SessionState> {
  static const _baseUrlKey = 'base_url';
  static const _accessKey = 'access_token';
  static const _refreshKey = 'refresh_token';
  static const _userKey = 'user';

  KeyValueStore get _store => ref.read(keyValueStoreProvider);

  @override
  SessionState build() => const SessionState();

  /// Loads the stored session; call once at start.
  Future<void> restore() async {
    final baseUrl = await _store.read(_baseUrlKey) ?? AppConfig.defaultBaseUrl;
    final access = await _store.read(_accessKey);
    final refresh = await _store.read(_refreshKey);
    final userJson = await _store.read(_userKey);
    if (access == null || refresh == null || userJson == null) {
      state = SessionState(status: SessionStatus.signedOut, baseUrl: baseUrl);
      return;
    }
    state = SessionState(
      status: SessionStatus.signedIn,
      baseUrl: baseUrl,
      tokens: Tokens(access: access, refresh: refresh),
      user: User.fromJson(jsonDecode(userJson) as Map<String, dynamic>),
    );
  }

  Future<void> setBaseUrl(String baseUrl) async {
    await _store.write(_baseUrlKey, baseUrl);
    state = SessionState(
      status: state.status,
      baseUrl: baseUrl,
      user: state.user,
      tokens: state.tokens,
    );
  }

  Future<void> signIn(Tokens tokens, User user) async {
    await _store.write(_accessKey, tokens.access);
    await _store.write(_refreshKey, tokens.refresh);
    await _store.write(_userKey, jsonEncode(user.toJson()));
    state = SessionState(
      status: SessionStatus.signedIn,
      baseUrl: state.baseUrl,
      tokens: tokens,
      user: user,
    );
  }

  /// Stores a renewed token pair; the user stays the same.
  Future<void> updateTokens(Tokens tokens) async {
    final user = state.user;
    if (user != null) await signIn(tokens, user);
  }

  Future<void> signOut() async {
    await _store.delete(_accessKey);
    await _store.delete(_refreshKey);
    await _store.delete(_userKey);
    state = SessionState(
      status: SessionStatus.signedOut,
      baseUrl: state.baseUrl,
    );
  }
}

final sessionProvider = NotifierProvider<SessionController, SessionState>(
  SessionController.new,
);
