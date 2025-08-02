class AuthService {
  Future<bool> signIn(String username, String password) async {
    await Future.delayed(const Duration(seconds: 1)); // Simulate network call
    // Add your actual authentication logic here
    if (username.isEmpty || password.isEmpty) {
      return false;
    }
    // Example: return true if credentials are valid
    return username == "demo" && password == "password";
  }

  Future<bool> signUp(String email, String password, String username) async {
    await Future.delayed(const Duration(seconds: 1));
    return email.isNotEmpty && password.isNotEmpty && username.isNotEmpty;
  }

  Future<void> resetPassword(String email) async {
    await Future.delayed(const Duration(seconds: 1));
    if (email.isEmpty) throw Exception("Email cannot be empty");
  }
}
