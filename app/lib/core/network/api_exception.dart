import 'package:dio/dio.dart';

/// An error answer of the API (`{"error": {"code", "message"}}`) or a failed
/// connection (`code == network`).
class ApiException implements Exception {
  const ApiException({
    required this.code,
    required this.message,
    this.statusCode,
    this.body,
  });

  factory ApiException.fromDio(DioException error) {
    final response = error.response;
    if (response == null) {
      return ApiException(code: network, message: error.message ?? 'network');
    }
    final data = response.data;
    if (data is Map<String, dynamic>) {
      final detail = data['error'];
      if (detail is Map<String, dynamic>) {
        return ApiException(
          code: detail['code'] as String? ?? unknown,
          message: detail['message'] as String? ?? '',
          statusCode: response.statusCode,
          body: data,
        );
      }
    }
    return ApiException(
      code: response.statusCode == 422 ? validation : unknown,
      message: response.statusMessage ?? '',
      statusCode: response.statusCode,
    );
  }

  static const network = 'network';
  static const validation = 'validation';
  static const unknown = 'unknown';

  final String code;
  final String message;
  final int? statusCode;

  /// Whole response body, e.g. `current` of a version conflict.
  final Map<String, dynamic>? body;

  @override
  String toString() => 'ApiException($statusCode, $code, $message)';
}

/// Runs an API call and turns Dio errors into [ApiException].
Future<T> apiCall<T>(Future<T> Function() request) async {
  try {
    return await request();
  } on DioException catch (error) {
    throw ApiException.fromDio(error);
  }
}
