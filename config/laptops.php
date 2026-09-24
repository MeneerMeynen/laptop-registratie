<?php

return [

    /*
    | Versie van de applicatie (rechtsonder in de UI getoond als vX.Y.Z).
    | Bump deze waarde bij een release (semantic versioning).
    */
    'version' => '2.0.0',

    /*
    | Eén gedeelde login voor de hele applicatie (geen users-tabel).
    | Zet AUTH_USERNAME en AUTH_PASSWORD in .env. Zonder wachtwoord kan
    | niemand inloggen.
    */
    'auth_username' => env('AUTH_USERNAME', 'admin'),
    'auth_password' => env('AUTH_PASSWORD', ''),

    /*
    | Map waarin laptopfoto's bewaard worden (buiten de publieke webroot;
    | foto's worden via een route achter de login geserveerd).
    */
    'upload_dir' => env('UPLOAD_DIR', storage_path('app/uploads/laptops')),

];
