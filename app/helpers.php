<?php

if (! function_exists('static_v')) {
    /** /static/<pad>?v=<mtime> voor cache-busting bij een deploy. */
    function static_v(string $path): string
    {
        $file = public_path('static/'.$path);
        $mtime = is_file($file) ? filemtime($file) : 0;

        return "/static/{$path}?v={$mtime}";
    }
}
