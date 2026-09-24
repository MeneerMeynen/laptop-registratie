<?php

use App\Support\DetailException;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\HttpKernel\Exception\HttpExceptionInterface;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware): void {
        //
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        // Validatie- en domeinfouten ({"detail": ...}) zijn verwacht gedrag, geen serverfouten.
        $exceptions->dontReport(DetailException::class);

        $wantsJson = fn (Request $request) => $request->is('api/*') || $request->expectsJson();

        // HTTP-fouten van de API in FastAPI-formaat: {"detail": "..."}.
        // (Laravel zet TokenMismatch- en PostTooLarge-excepties vooraf om naar HTTP 419 / 413.)
        $exceptions->render(function (HttpExceptionInterface $e, Request $request) use ($wantsJson) {
            $status = $e->getStatusCode();

            // Verlopen sessie / ontbrekend CSRF-token: HTMX terug naar de loginpagina.
            if ($status === 419 && $request->headers->has('HX-Request')) {
                return response('', 204)->header('HX-Redirect', '/login');
            }
            if (! $wantsJson($request)) {
                return null;
            }

            $message = match (true) {
                $status === 419 => 'Sessie verlopen. Vernieuw de pagina en log opnieuw in.',
                $status === 413 => 'Upload is te groot voor de server (zie post_max_size in PHP).',
                default => $e->getMessage() ?: (Response::$statusTexts[$status] ?? 'Error'),
            };

            return response()->json(['detail' => $message], $status, $e->getHeaders());
        });

        $exceptions->shouldRenderJsonWhen($wantsJson);
    })->create();
