<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Volledig schema van de oorspronkelijke FastAPI/Alembic-app (revisie 0013).
 *
 * Tabel- en kolomnamen zijn identiek gehouden, zodat een bestaande
 * MariaDB-database van de Python-versie rechtstreeks hergebruikt kan worden:
 * tabellen die al bestaan worden overgeslagen (Schema::hasTable).
 */
return new class extends Migration
{
    public function up(): void
    {
        if (! Schema::hasTable('students')) {
            Schema::create('students', function (Blueprint $table) {
                $table->string('stamnummer', 50)->primary();
                $table->string('instellingsnummer', 50)->nullable();
                $table->string('naam', 100)->nullable();
                $table->string('voornaam', 100)->nullable();
                $table->string('klas', 50)->nullable();
                $table->string('klascode', 50)->nullable();
                $table->string('klasnummer', 50)->nullable();
                $table->string('gebruikersnaam', 100)->nullable();
                $table->string('pointer', 100)->nullable();
                $table->dateTime('last_import')->nullable();
                // Leerkrachten staan in dezelfde tabel zodat koppelen, issues en exports gelijk werken.
                $table->boolean('is_leerkracht')->default(false);
                // Leerkrachtafkorting uit de leerkrachten-export (bv. ANTCE).
                $table->string('afkorting', 20)->nullable();
            });
        }

        if (! Schema::hasTable('storage_cabinets')) {
            Schema::create('storage_cabinets', function (Blueprint $table) {
                $table->increments('id');
                $table->string('name', 100)->unique('uq_storage_cabinets_name');
                $table->string('location', 100)->nullable();
                $table->text('description')->nullable();
                $table->integer('capacity')->nullable();
                $table->dateTime('created_at');
                // "kast": laptops mogen niet aan een leerling gekoppeld worden;
                // "magazijn": laptops kunnen later aan een leerling toegekend worden.
                $table->string('kind', 20)->default('kast');
            });
        }

        if (! Schema::hasTable('laptops')) {
            Schema::create('laptops', function (Blueprint $table) {
                $table->increments('id');
                // nullable: "eigen laptop"-records hebben geen serienummer.
                $table->string('serial_number', 100)->nullable();
                // nullable: reserve- en kastlaptops hebben geen leerling.
                $table->string('stamnummer', 50)->nullable()->index('ix_laptops_stamnummer');
                $table->boolean('eigen_laptop')->default(false);
                $table->dateTime('linked_at')->nullable();
                $table->dateTime('unlinked_at')->nullable();
                $table->boolean('is_reserve')->default(false);
                $table->string('alias', 100)->nullable();
                $table->unsignedInteger('storage_cabinet_id')->nullable()->index('ix_laptops_storage_cabinet_id');
                $table->boolean('hoes_ingeleverd')->default(true);
                $table->boolean('oplader_ingeleverd')->default(true);

                $table->index(['serial_number', 'unlinked_at'], 'ix_laptops_serial_active');
                $table->foreign('stamnummer')->references('stamnummer')->on('students')->cascadeOnDelete();
                $table->foreign('storage_cabinet_id', 'fk_laptops_storage_cabinet_id')
                    ->references('id')->on('storage_cabinets')->nullOnDelete();
            });
        }

        if (! Schema::hasTable('laptop_issues')) {
            Schema::create('laptop_issues', function (Blueprint $table) {
                $table->increments('id');
                $table->string('serial_number', 100)->index('ix_laptop_issues_serial_number');
                $table->text('description');
                $table->date('reported_date');
                $table->string('status', 20)->default('aangemeld')->index('ix_laptop_issues_status');
                $table->text('solution')->nullable();
                $table->dateTime('created_at')->useCurrent();
                $table->string('category', 50)->nullable();
                $table->unsignedInteger('reserve_laptop_id')->nullable()->index('ix_laptop_issues_reserve_laptop_id');

                $table->foreign('reserve_laptop_id', 'fk_laptop_issues_reserve_laptop_id')
                    ->references('id')->on('laptops')->nullOnDelete();
            });
        }

        if (! Schema::hasTable('laptop_issue_entries')) {
            Schema::create('laptop_issue_entries', function (Blueprint $table) {
                $table->increments('id');
                $table->unsignedInteger('issue_id')->index('ix_laptop_issue_entries_issue_id');
                $table->text('text');
                $table->dateTime('created_at')->useCurrent();

                $table->foreign('issue_id')->references('id')->on('laptop_issues')->cascadeOnDelete();
            });
        }

        if (! Schema::hasTable('laptop_photos')) {
            Schema::create('laptop_photos', function (Blueprint $table) {
                $table->increments('id');
                $table->string('serial_number', 100)->index('ix_laptop_photos_serial_number');
                $table->string('filename', 255);
                $table->dateTime('created_at')->useCurrent();
            });
        }

        if (! Schema::hasTable('sessions')) {
            Schema::create('sessions', function (Blueprint $table) {
                $table->string('id')->primary();
                $table->foreignId('user_id')->nullable()->index();
                $table->string('ip_address', 45)->nullable();
                $table->text('user_agent')->nullable();
                $table->longText('payload');
                $table->integer('last_activity')->index();
            });
        }
    }

    public function down(): void
    {
        Schema::dropIfExists('sessions');
        Schema::dropIfExists('laptop_photos');
        Schema::dropIfExists('laptop_issue_entries');
        Schema::dropIfExists('laptop_issues');
        Schema::dropIfExists('laptops');
        Schema::dropIfExists('storage_cabinets');
        Schema::dropIfExists('students');
    }
};
