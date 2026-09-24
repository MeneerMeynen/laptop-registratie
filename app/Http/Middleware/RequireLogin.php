<?php

namespace App\Http\Middleware;

use App\Http\Controllers\AuthController;
use Closure;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * Laat een request alleen door als er een ingelogde sessie is.
 *
 * Niet ingelogd:
 * - HTMX-requests krijgen 204 + HX-Redirect: /login
 * - HTML-requests (Accept: text/html) een 303-redirect naar /login?next=…
 * - alle andere (API) requests 401 {"detail": "Not authenticated"}
 */
class RequireLogin
{
    public function handle(Request $request, Closure $next): Response
    {
        if ($request->session()->get(AuthController::SESSION_USER_KEY)) {
            return $next($request);
        }

        if ($request->headers->has('HX-Request')) {
            return response('', 204)->header('HX-Redirect', '/login');
        }

        if (str_contains((string) $request->header('Accept', ''), 'text/html')) {
            $nextUrl = '/'.ltrim($request->path(), '/');
            $query = $request->server('QUERY_STRING');
            if ($query) {
                $nextUrl .= '?'.$query;
            }

            return new RedirectResponse('/login?next='.rawurlencode($nextUrl), 303);
        }

        return new JsonResponse(['detail' => 'Not authenticated'], 401);
    }
}
