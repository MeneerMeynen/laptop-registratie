<?php

namespace App\Http\Controllers;

use App\Support\Fmt;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Response;

/** Eén gedeelde login (gebruikersnaam/wachtwoord uit .env). */
class AuthController extends Controller
{
    public const SESSION_USER_KEY = 'user';

    /** Alleen interne paden als redirectdoel toestaan (geen //evil.example). */
    public static function safeNext(?string $next): string
    {
        if ($next && str_starts_with($next, '/') && ! str_starts_with($next, '//') && ! str_starts_with($next, '/\\')) {
            return $next;
        }

        return '/';
    }

    public static function verifyCredentials(string $username, string $password): bool
    {
        $expectedUser = (string) config('laptops.auth_username');
        $expectedPass = (string) config('laptops.auth_password');
        if ($expectedPass === '') {
            return false;
        }
        // Beide vergelijkingen altijd uitvoeren (constante tijd).
        $userOk = hash_equals($expectedUser, $username);
        $passOk = hash_equals($expectedPass, $password);

        return $userOk && $passOk;
    }

    public function showLogin(Request $request): Response
    {
        return response()->view('login', [
            'next' => self::safeNext($request->query('next')),
            'error' => Fmt::bool($request->query('error')),
        ]);
    }

    public function login(Request $request): Response|RedirectResponse
    {
        $target = self::safeNext($request->input('next'));
        $username = (string) $request->input('username', '');
        $password = (string) $request->input('password', '');

        if (! self::verifyCredentials($username, $password)) {
            return response()->view('login', ['next' => $target, 'error' => true], 401);
        }

        // Nieuwe sessie-ID na inloggen (bescherming tegen session fixation).
        $request->session()->regenerate();
        $request->session()->put(self::SESSION_USER_KEY, $username);

        return new RedirectResponse($target, 303);
    }

    public function logout(Request $request): RedirectResponse
    {
        $request->session()->forget(self::SESSION_USER_KEY);
        $request->session()->invalidate();
        $request->session()->regenerateToken();

        return new RedirectResponse('/login', 303);
    }
}
