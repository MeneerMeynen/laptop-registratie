<?php

namespace Tests\Feature;

use Tests\TestCase;

class AuthTest extends TestCase
{
    protected bool $loggedIn = false;

    public function test_root_redirects_to_login_when_anonymous(): void
    {
        $resp = $this->get('/', ['Accept' => 'text/html']);
        $resp->assertStatus(303);
        $this->assertStringStartsWith('/login', $resp->headers->get('Location'));
    }

    public function test_api_returns_401_when_anonymous(): void
    {
        $this->get('/api/students', ['Accept' => '*/*'])->assertStatus(401)->assertExactJson(['detail' => 'Not authenticated']);
    }

    public function test_htmx_request_returns_redirect_header(): void
    {
        $this->get('/ui/students/list', ['HX-Request' => 'true'])
            ->assertStatus(204)
            ->assertHeader('HX-Redirect', '/login');
    }

    public function test_login_page_is_public(): void
    {
        $this->get('/login')->assertOk()->assertSee('Inloggen');
    }

    public function test_static_files_exist_in_public_dir(): void
    {
        // Statische bestanden worden rechtstreeks door de webserver geserveerd.
        $this->assertFileExists(public_path('static/css/style.css'));
        $this->assertFileExists(public_path('static/js/csrf.js'));
        $this->assertFileExists(public_path('static/zxing-wasm/zxing_full.wasm'));
    }

    public function test_bad_password_returns_401(): void
    {
        $this->post('/login', ['username' => 'test', 'password' => 'wrong'])->assertStatus(401);
    }

    public function test_good_login_sets_session_and_redirects(): void
    {
        $this->post('/login', ['username' => 'test', 'password' => 'test'])
            ->assertStatus(303)
            ->assertHeader('Location', '/');

        $this->get('/api/students')->assertOk();
    }

    public function test_login_honours_safe_next(): void
    {
        $this->post('/login', ['username' => 'test', 'password' => 'test', 'next' => '/photos'])
            ->assertStatus(303)
            ->assertHeader('Location', '/photos');
    }

    public function test_login_rejects_external_next(): void
    {
        $this->post('/login', ['username' => 'test', 'password' => 'test', 'next' => '//evil.example/x'])
            ->assertStatus(303)
            ->assertHeader('Location', '/');
    }

    public function test_empty_password_config_blocks_login(): void
    {
        config(['laptops.auth_password' => '']);

        $this->post('/login', ['username' => 'test', 'password' => ''])->assertStatus(401);
    }

    public function test_logout_clears_session(): void
    {
        $this->withSession(['user' => 'test']);

        $this->post('/logout')->assertStatus(303)->assertHeader('Location', '/login');
        $this->get('/api/students', ['Accept' => '*/*'])->assertStatus(401);
    }

    public function test_photos_are_behind_login(): void
    {
        $this->get('/uploads/laptops/ABC/0123456789abcdef0123456789abcdef.jpg', ['Accept' => 'image/*'])->assertStatus(401);
    }
}
