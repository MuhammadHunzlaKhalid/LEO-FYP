import 'package:flutter/material.dart';
import 'api_service.dart';
import 'session.dart';

class MyLogin extends StatefulWidget {
  const MyLogin({super.key});
  @override
  State<MyLogin> createState() => _MyLoginState();
}

class _MyLoginState extends State<MyLogin> {
  final _userCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  bool _loading   = false;
  bool _obscure   = true;
  String? _error;

  List<Map<String, dynamic>> _patients = [];
  bool _patientsLoading = true;

  @override
  void initState() { super.initState(); _loadPatients(); }

  Future<void> _loadPatients() async {
    final list = await ApiService.getPatients();
    if (!mounted) return;
    setState(() { _patients = list; _patientsLoading = false; });
  }

  Future<void> _signIn([String? username]) async {
    final u = (username ?? _userCtrl.text).trim();
    if (u.isEmpty) {
      setState(() => _error = 'Select a patient or enter a username.');
      return;
    }
    setState(() { _loading = true; _error = null; });
    final profile = await ApiService.login(u);
    setState(() => _loading = false);
    if (profile != null) {
      final name = (profile['profile']?['personal']?['name'] as String?) ?? u;
      Session.set(u, name: name);
      if (mounted) Navigator.pushReplacementNamed(context, 'home');
    } else {
      setState(() => _error = 'User "$u" not found. Please Sign Up first.');
    }
  }

  void _googleSignIn() {
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
      content: Text('Add firebase_auth + google_sign_in packages to enable Google login'),
    ));
  }

  @override
  void dispose() { _userCtrl.dispose(); _passCtrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        image: DecorationImage(
            image: AssetImage('assets/backgrund.jpg'), fit: BoxFit.cover)),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        body: Stack(children: [
          Container(
            padding: const EdgeInsets.only(left: 35, top: 100),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: const [
              Text('Welcome Back', style: TextStyle(color: Colors.white,
                  fontSize: 33, fontWeight: FontWeight.w700)),
              SizedBox(height: 6),
              Text('Select patient or sign in', style: TextStyle(
                  color: Colors.white70, fontSize: 14)),
            ]),
          ),
          SingleChildScrollView(
            child: Container(
              padding: EdgeInsets.only(
                top: MediaQuery.of(context).size.height * 0.28,
                right: 35, left: 35,
              ),
              child: Column(children: [

                // ── Patient quick-select tiles from MongoDB ─
                if (_patientsLoading)
                  const Padding(
                    padding: EdgeInsets.only(bottom: 12),
                    child: Row(children: [
                      SizedBox(width: 14, height: 14,
                          child: CircularProgressIndicator(
                              color: Colors.white70, strokeWidth: 2)),
                      SizedBox(width: 8),
                      Text('Loading patients from database...',
                          style: TextStyle(color: Colors.white70, fontSize: 12)),
                    ]),
                  )
                else if (_patients.isNotEmpty) ...[
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.white30),
                    ),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                      const Text('REGISTERED PATIENTS',
                          style: TextStyle(color: Colors.white60,
                              fontSize: 10, letterSpacing: 1,
                              fontWeight: FontWeight.w600)),
                      const SizedBox(height: 10),
                      ..._patients.map((p) {
                        final u = p['username'] as String;
                        final n = p['name'] as String? ?? u;
                        return GestureDetector(
                          onTap: _loading ? null : () => _signIn(u),
                          child: Container(
                            margin: const EdgeInsets.only(bottom: 8),
                            padding: const EdgeInsets.symmetric(
                                horizontal: 16, vertical: 10),
                            decoration: BoxDecoration(
                              color: Colors.white.withOpacity(0.25),
                              borderRadius: BorderRadius.circular(10),
                              border: Border.all(color: Colors.white54),
                            ),
                            child: Row(children: [
                              const CircleAvatar(radius: 16,
                                  backgroundColor: Color(0xff4c505b),
                                  child: Icon(Icons.person,
                                      color: Colors.white, size: 16)),
                              const SizedBox(width: 12),
                              Expanded(child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                Text(n, style: const TextStyle(
                                    color: Colors.white,
                                    fontWeight: FontWeight.bold,
                                    fontSize: 14)),
                                Text('@$u', style: const TextStyle(
                                    color: Colors.white60, fontSize: 11)),
                              ])),
                              const Icon(Icons.arrow_forward_ios,
                                  color: Colors.white54, size: 14),
                            ]),
                          ),
                        );
                      }),
                    ]),
                  ),
                  const SizedBox(height: 14),
                  Row(children: [
                    Expanded(child: Divider(color: Colors.white.withOpacity(0.3))),
                    const Padding(
                      padding: EdgeInsets.symmetric(horizontal: 10),
                      child: Text('OR', style: TextStyle(
                          color: Colors.white54, fontSize: 11)),
                    ),
                    Expanded(child: Divider(color: Colors.white.withOpacity(0.3))),
                  ]),
                  const SizedBox(height: 10),
                ],

                // ── Username ───────────────────────────────
                TextField(
                  controller: _userCtrl,
                  decoration: InputDecoration(
                    fillColor: Colors.grey.shade100, filled: true,
                    hintText: 'Username',
                    prefixIcon: const Icon(Icons.person_outline),
                    border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10)),
                  ),
                  onSubmitted: (_) => _signIn(),
                ),
                const SizedBox(height: 16),

                // ── Password ───────────────────────────────
                TextField(
                  controller: _passCtrl,
                  obscureText: _obscure,
                  decoration: InputDecoration(
                    fillColor: Colors.grey.shade100, filled: true,
                    hintText: 'Password',
                    prefixIcon: const Icon(Icons.lock_outline),
                    suffixIcon: IconButton(
                      icon: Icon(_obscure ? Icons.visibility_off
                          : Icons.visibility, color: Colors.grey),
                      onPressed: () => setState(() => _obscure = !_obscure),
                    ),
                    border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10)),
                  ),
                  onSubmitted: (_) => _signIn(),
                ),

                // ── Error ──────────────────────────────────
                if (_error != null) ...[
                  const SizedBox(height: 10),
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: Colors.red.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.redAccent),
                    ),
                    child: Row(children: [
                      const Icon(Icons.error_outline,
                          color: Colors.redAccent, size: 16),
                      const SizedBox(width: 8),
                      Expanded(child: Text(_error!, style: const TextStyle(
                          color: Colors.redAccent, fontSize: 13))),
                    ]),
                  ),
                ],

                const SizedBox(height: 24),

                // ── Sign In (original style) ───────────────
                Row(mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                  TextButton(
                    onPressed: _loading ? null : () => _signIn(),
                    child: const Text('Sign In', style: TextStyle(
                        color: Colors.white, fontSize: 27,
                        fontWeight: FontWeight.w700)),
                  ),
                  CircleAvatar(
                    radius: 30,
                    backgroundColor: const Color(0xff4c505b),
                    child: _loading
                        ? const CircularProgressIndicator(
                            color: Colors.white, strokeWidth: 2)
                        : IconButton(
                            color: Colors.white,
                            onPressed: () => _signIn(),
                            icon: const Icon(Icons.arrow_forward)),
                  ),
                ]),

                const SizedBox(height: 16),

                // ── Google Sign In ─────────────────────────
                SizedBox(width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _googleSignIn,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.white,
                      foregroundColor: Colors.black87,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10)),
                    ),
                    child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                      Container(width: 24, height: 24,
                          decoration: const BoxDecoration(
                              color: Colors.red, shape: BoxShape.circle),
                          child: const Center(child: Text('G',
                              style: TextStyle(color: Colors.white,
                                  fontWeight: FontWeight.bold,
                                  fontSize: 14)))),
                      const SizedBox(width: 10),
                      const Text('Continue with Google',
                          style: TextStyle(fontWeight: FontWeight.w600,
                              fontSize: 15)),
                    ]),
                  )),

                const SizedBox(height: 16),

                Row(mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                  TextButton(
                    onPressed: () => Navigator.pushNamed(context, 'register'),
                    child: const Text('Sign Up', style: TextStyle(
                        decoration: TextDecoration.underline,
                        fontSize: 16, color: Colors.white)),
                  ),
                  TextButton(
                    onPressed: () {},
                    child: const Text('Forget Password', style: TextStyle(
                        decoration: TextDecoration.underline,
                        fontSize: 16, color: Colors.white)),
                  ),
                ]),
                const SizedBox(height: 40),
              ]),
            ),
          ),
        ]),
      ),
    );
  }
}
