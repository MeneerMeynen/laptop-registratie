<?php

namespace App\Http\Controllers;

use App\Support\DetailException;
use Illuminate\Http\Request;

abstract class Controller
{
    /** JSON-body als array; 422 als de body geen JSON-object is (zoals FastAPI). */
    protected function body(Request $request, bool $optional = false): array
    {
        $raw = $request->getContent();
        if (trim($raw) === '') {
            if ($optional) {
                return [];
            }
            throw new DetailException(422, 'Request body ontbreekt.');
        }
        $data = json_decode($raw, true);
        if (! is_array($data) || (array_is_list($data) && $data !== [])) {
            throw new DetailException(422, 'Ongeldige JSON-body.');
        }

        return $data;
    }

    protected function requireString(array $data, string $key): string
    {
        if (! array_key_exists($key, $data) || ! is_scalar($data[$key]) || is_bool($data[$key])) {
            throw new DetailException(422, "Veld '{$key}' is verplicht.");
        }

        return (string) $data[$key];
    }

    protected function optString(array $data, string $key): ?string
    {
        $value = $data[$key] ?? null;
        if ($value === null) {
            return null;
        }
        if (! is_scalar($value) || is_bool($value)) {
            throw new DetailException(422, "Veld '{$key}' moet tekst zijn.");
        }

        return (string) $value;
    }

    protected function optInt(array $data, string $key): ?int
    {
        $value = $data[$key] ?? null;
        if ($value === null) {
            return null;
        }
        if (is_bool($value) || filter_var($value, FILTER_VALIDATE_INT) === false) {
            throw new DetailException(422, "Veld '{$key}' moet een geheel getal zijn.");
        }

        return (int) $value;
    }

    protected function optBool(array $data, string $key, bool $default): bool
    {
        $value = $data[$key] ?? null;
        if ($value === null) {
            return $default;
        }
        $bool = filter_var($value, FILTER_VALIDATE_BOOLEAN, FILTER_NULL_ON_FAILURE);
        if ($bool === null) {
            throw new DetailException(422, "Veld '{$key}' moet true of false zijn.");
        }

        return $bool;
    }

    /** Lijst van strings (bv. stamnummers of serienummers). */
    protected function stringList(array $data, string $key): array
    {
        $value = $data[$key] ?? null;
        if (! is_array($value)) {
            throw new DetailException(422, "Veld '{$key}' moet een lijst zijn.");
        }

        return array_map(fn ($v) => (string) $v, array_values($value));
    }

    /** Datum JJJJ-MM-DD valideren. */
    protected function requireDate(array $data, string $key): string
    {
        return $this->validDate($this->requireString($data, $key), $key);
    }

    protected function validDate(string $value, string $key): string
    {
        $parts = explode('-', $value);
        if (! preg_match('/^\d{4}-\d{2}-\d{2}\z/', $value) || ! checkdate((int) $parts[1], (int) $parts[2], (int) $parts[0])) {
            throw new DetailException(422, "Veld '{$key}' moet een geldige datum zijn (JJJJ-MM-DD).");
        }

        return $value;
    }
}
