<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Student extends Model
{
    protected $primaryKey = 'stamnummer';

    protected $keyType = 'string';

    public $incrementing = false;

    public $timestamps = false;

    protected $guarded = [];

    protected function casts(): array
    {
        return [
            'last_import' => 'datetime',
            'is_leerkracht' => 'boolean',
        ];
    }

    public function laptops(): HasMany
    {
        return $this->hasMany(Laptop::class, 'stamnummer', 'stamnummer');
    }
}
