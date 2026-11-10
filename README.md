# 💅 Holy Nails

<p align="center">
  <strong>Sistema Web de Gestión de Turnos para Salón de Manicuría & Nail Art</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Estado-En_Desarrollo-ff69b4?style=for-the-badge&logo=git&logoColor=white" alt="Estado del Proyecto" />
  <img src="https://img.shields.io/badge/Django-6.0-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django" />
  <img src="https://img.shields.io/badge/DRF-3.17-red?style=for-the-badge&logo=django&logoColor=white" alt="Django REST Framework" />
  <img src="https://img.shields.io/badge/SimpleJWT-5.5-black?style=for-the-badge&logo=json-web-tokens&logoColor=white" alt="JWT" />
  <img src="https://img.shields.io/badge/PostgreSQL-15%2B-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/React-19.0-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React" />
  <img src="https://img.shields.io/badge/Vite-8.0-646CFF?style=for-the-badge&logo=vite&logoColor=white" alt="Vite" />
  <img src="https://img.shields.io/badge/Bootstrap-5.3-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white" alt="Bootstrap" />
  <img src="https://img.shields.io/badge/Swagger-OpenAPI_3.0-85EA2D?style=for-the-badge&logo=swagger&logoColor=black" alt="Swagger" />
</p>

---

> 🚧 **Proyecto en desarrollo**
>
> **Holy Nails** se encuentra actualmente en proceso de desarrollo activo. La API REST backend está implementada y funcional, y la interfaz gráfica frontend (React) está construida y maquetada por fases. Algunas características y la integración entre frontend y backend se completarán progresivamente.

---

## 📸 Muestra Visual / Preview

<p align="center">
  <img src="./frontend/src/assets/hero.jpg" alt="Holy Nails Hero Preview" width="800" style="border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.15);" />
</p>

<p align="center">
  <em>Estética visual inspirada en un estilo moderno, femenino, cute y dark / gothic chic.</em>
</p>

> 💡 *Nota: Las capturas finales de interacción en tiempo real se actualizarán al culminar la etapa de integración frontend-backend.*

---

## 📌 Sobre el proyecto

**Holy Nails** es una plataforma web integral orientada a la gestión eficiente de agendamiento de turnos para un estudio o salón de manicuría.

### 🎯 Problema que busca resolver
El agendamiento informal a través de mensajes de texto genera inconvenientes frecuentes: solapamiento de turnos, falta de información sobre la duración o precios de los servicios (Semipermanente, Kapping, Esculpidas), y pérdida de tiempo organizativo tanto para la manicurista como para sus clientas.

### 💡 Solución propuesta
Holy Nails automatiza y centraliza la reserva de citas en línea:
- **Para las clientas**: Permite explorar el catálogo de servicios, conocer precios/duraciones y solicitar turnos disponibles en horarios comerciales definidos.
- **Para la administración**: Facilita el control de la agenda, la actualización del catálogo de servicios y la administración de los estados de cada turno (`pendiente`, `confirmado`, `cancelado`).

---

## 🚧 Estado del proyecto

En la siguiente tabla se detalla el estado actual de cada componente del sistema:

| Estado | Módulo / Funcionalidad | Descripción |
| :---: | --- | --- |
| ✅ | **API REST (Django + DRF)** | Arquitectura backend estructurada con endpoints RESTful para autenticación, usuarios, servicios y turnos. |
| ✅ | **Autenticación JWT** | Autenticación segura mediante JSON Web Tokens (`SimpleJWT`) con renovación automática de tokens. |
| ✅ | **Modelo de Datos y Validaciones** | Restricción de turnos duplicados en misma fecha/hora, horario de atención (09:00 a 20:00 hs) y validación de fechas pasadas. |
| ✅ | **Control de Permisos por Roles** | Permisos personalizados en API (`IsAuthenticated`, `IsAdmin`, `IsOwnerOrAdmin`, `EsProfesionalOAdmin`) según el rol del usuario. |
| ✅ | **Documentación OpenAPI 3 / Swagger** | Documentación interactiva de la API accesible públicamente mediante Swagger UI (`drf-spectacular`). |
| ✅ | **Interfaz de Usuario Frontend (React)** | Vistas principales desarrolladas y maquetadas con Bootstrap: Home, Galería, Agendar, Mis Turnos, Perfil y Panel Admin. |
| ✅ | **Protección de Rutas en Frontend** | Enrutamiento protegido por autenticación y roles mediante componentes `ProtectedRoute` y `RoleRoute`. |
| 🚧 | **Conexión Frontend ↔ Backend** | `AuthContext` ya utiliza la API Django para registro, login y perfil con JWT; la integración de los flujos de turnos y administración continúa pendiente. |
| 🚧 | **Selección Dinámica de Horarios** | Desplegable de franjas horarias disponibles según la duración del servicio seleccionado y turnos ocupados. |
| 📋 | **Notificaciones Automáticas** | Confirmaciones y recordatorios de turnos vía email o WhatsApp. |
| 📋 | **Historial y Reportes de Gestión** | Indicadores administrativos sobre los servicios más solicitados e historial de atenciones por cliente. |

---

> 🔐 **Nota de seguridad — Autenticación y sesión**
>
> El login y el registro del frontend se procesan en la API Django; `AuthContext` consulta y actualiza el perfil mediante esa API y usa JWT. Los tokens se conservan en `localStorage` del navegador, por lo que deben protegerse frente a XSS y transmitirse únicamente por HTTPS en producción.
>
> - Los permisos efectivos se validan en el backend; las protecciones visuales de rutas en el frontend no sustituyen esa autorización.

---

## ✨ Funcionalidades

### 🔐 Autenticación y Cuentas
- [x] Registro de usuarias/os con asignación automática del rol `CLIENTE`.
- [x] Inicio de sesión y generación de tokens JWT de acceso y refresco.
- [x] Consulta y actualización del perfil de usuario (`/api/auth/profile/`).

### 💅 Gestión de Servicios (Catálogo)
- [x] Consulta pública de servicios activos (nombre, duración, precio).
- [x] Gestión administrativa (alta, baja lógica y modificación) reservada exclusivamente al rol `ADMIN`.

### 📅 Gestión de Turnos
- [x] Reserva de turnos asociada a un servicio válido y fecha/hora elegida.
- [x] Validación automática en backend:
  - No permite reservar en fechas pasadas.
  - No permite reservar fuera del rango de atención (09:00 a 20:00 hs).
  - Impide el solapamiento de dos turnos en la misma fecha y hora (`UniqueConstraint`).
- [x] Gestión de estados del turno: `pendiente`, `confirmado` y `cancelado`.
- [x] Filtro de visibilidad: Las clientas solo pueden consultar y gestionar **sus propios turnos**, mientras que el administrador tiene acceso a la agenda completa.

---

## 👥 Roles y permisos

El sistema contempla la siguiente distinción de roles tanto en backend como en frontend:

| Rol | Ámbito | Descripción y Permisos |
| --- | --- | --- |
| **`CLIENTE`** | App / Frontend / API | Rol por defecto asignado al registrarse. Puede explorar servicios activos, crear reservas de turnos y ver/gestionar únicamente sus propios turnos. |
| **`ADMIN`** | App / Frontend / API | Administrador de la aplicación. Es el único que puede gestionar el catálogo de servicios completo, crear cuentas de `PERSONAL` (alta administrativa con Profesional vinculado), visualizar todos los turnos del salón, cambiar estados de reservas y acceder al panel `/admin` en el frontend. |
| **`PERSONAL`** | App / Frontend / API | Cuenta de trabajadora/or creada por `ADMIN` junto con su registro `Profesional` vinculado (invariante: todo `PERSONAL` tiene Profesional). Gestiona sus propias disponibilidades y consulta su agenda laboral desde `/mi-agenda` (`?como_profesional=true`); no gestiona servicios ni participa del flujo de reservas. |
| **`Django Staff`** | Panel Admin Django | Superusuario o staff de Django con acceso al panel nativo de administración (`/admin/`) y permisos administrativos automáticos en la API REST. |

---

## 🛠️ Tecnologías utilizadas

| Tecnología | Categoría | Propósito en el Proyecto |
| --- | --- | --- |
| **Python 3.13** | Lenguaje | Lenguaje principal del servidor backend |
| **Django 6.0** | Framework Backend | Estructura web, ORM y panel de administración |
| **Django REST Framework 3.17** | API REST | Construcción de endpoints, serializadores y vistas |
| **SimpleJWT 5.5** | Autenticación | Manejo de autenticación por JSON Web Tokens |
| **drf-spectacular 0.29** | Documentación | Generación de especificación OpenAPI 3 y Swagger UI |
| **PostgreSQL / psycopg 3** | Base de Datos | Base de datos relacional para entornos de desarrollo y producción |
| **React 19** | Biblioteca Frontend | Creación de componentes e interfaz de usuario SPA |
| **Vite 8** | Build Tool / Bundler | Entorno de desarrollo rápido y empaquetador para React |
| **Bootstrap 5.3** | Framework CSS | Maquetado responsive, grillas y componentes de diseño |
| **React Router DOM 7** | Navegación | Gestión de rutas, navegación SPA y guards de autorización |

---

## 📊 Modelo de Datos

### Entidades Principales

#### 👤 Usuario (`users.User`)
*Extiende `AbstractUser` de Django*
- `id`: Identificador único (PK).
- `username`: Nombre de usuario único.
- `email`: Correo electrónico único.
- `nombre`: Nombre y apellido del usuario.
- `role`: Rol del sistema (`ADMIN`, `CLIENTE`, `PERSONAL`).

#### 💅 Servicio (`core.Servicio`)
- `id`: Identificador del servicio (PK).
- `nombre`: Nombre del servicio (ej. Semipermanente, Kapping, Esculpidas).
- `duracion`: Duración estimada (`DurationField` >= 1 min).
- `precio`: Precio en pesos (`DecimalField` >= 0).
- `is_active`: Estado de visibilidad (Baja lógica).

#### 📅 Turno (`core.Turno`)
- `id`: Identificador del turno (PK).
- `fecha`: Fecha de la cita (`DateField`).
- `hora`: Hora de la cita (`TimeField`, entre 09:00 y 20:00 hs).
- `usuario`: Clave foránea referenciando a `User`.
- `servicio`: Clave foránea referenciando a `Servicio` (SET_NULL al eliminar).
- `estado`: Estado de la reserva (`pendiente`, `confirmado`, `cancelado`).

### Reglas de Negocio
1. Un usuario debe autenticarse para reservar un turno.
2. **Restricción de Unicidad**: No pueden existir dos turnos registrados con la misma fecha y hora (`UniqueConstraint(fields=['fecha', 'hora'])`).
3. La fecha de reserva no puede ser anterior a la fecha actual.
4. Las reservas solo se permiten en la franja horaria de 09:00 a 20:00 hs.

---

## 📁 Estructura del proyecto

```text
Programacion1/
├── config/                      # Configuración principal del proyecto Django
│   ├── settings.py              # Ajustes de Django (Apps, DB, SimpleJWT, CORS)
│   ├── urls.py                  # Enrutador principal y Swagger UI
│   ├── wsgi.py                  # Punto de entrada WSGI
│   └── asgi.py                  # Punto de entrada ASGI
├── core/                        # Aplicación principal de la lógica de negocio
│   ├── models.py                # Modelos de Servicio y Turno
│   ├── serializers.py           # Serializadores y validaciones de turnos/servicios
│   ├── views.py                 # ServicioViewSet y TurnoViewSet
│   ├── permissions.py           # Clases de permisos personalizados
│   └── urls.py                  # Enrutamiento API para servicios y turnos
├── users/                       # Aplicación de usuarios y autenticación
│   ├── models.py                # Modelo User personalizado con Roles
│   ├── serializers.py           # Serializadores de Registro y Perfil
│   ├── views.py                 # RegisterView, ProfileView y UserViewSet
│   └── urls.py                  # Rutas para /api/auth/ (login, register, profile)
├── frontend/                    # Aplicación cliente React + Vite
│   ├── src/
│   │   ├── assets/              # Imágenes de hero, catálogo y galería de trabajos
│   │   ├── components/          # Layout, Navbar, Footer, ProtectedRoute, RoleRoute
│   │   ├── context/             # AuthContext (Gestión de sesión de usuario)
│   │   └── views/               # Vistas: Home, Login, Register, Agendar, MisTurnos, Admin
│   ├── index.html               # Archivo HTML principal
│   ├── package.json             # Dependencias y scripts de frontend
│   └── vite.config.js           # Configuración del servidor de desarrollo Vite
├── manage.py                    # Script de administración de Django
├── requirements.txt             # Lista de dependencias Python
├── .env.example                 # Plantilla de variables de entorno para la base de datos
└── README.md                    # Documentación general del repositorio
```

---

## ⚙️ Instalación y Configuración

Siga las siguientes instrucciones para clonar y ejecutar el proyecto localmente.

### Prerrequisitos
- **Python** 3.10 o superior.
- **Node.js** v18 o superior y **npm**.
- Servidor **PostgreSQL** en ejecución local o remota.

---

### 1. Clonar el repositorio
```bash
git clone https://github.com/aguschamo/turnero-proyecto-programacion1.git
cd turnero-proyecto-programacion1
```

---

### 2. Configuración del Backend (Django)

1. **Crear y activar un entorno virtual**:
   - *En Windows (PowerShell)*:
     ```powershell
     python -m venv venv
     .\venv\Scripts\activate
     ```
   - *En Linux / macOS*:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

2. **Instalar dependencias del backend**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configurar variables de entorno**:
   Copiar el archivo de plantilla `.env.example` a un nuevo archivo `.env`:
   ```bash
   cp .env.example .env
   ```
   Generar una clave propia para este entorno:
   ```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```
   Copiar el resultado directamente al campo `SECRET_KEY` de `.env` (no compartirlo ni subirlo al repositorio). Luego editar `.env` e ingresar las credenciales de PostgreSQL de su entorno local:
   ```env
   SECRET_KEY=pegá_acá_la_clave_generada
   DB_NAME=programacion1_db
   DB_USER=postgres
   DB_PASSWORD=tu_contraseña_postgres
   DB_HOST=localhost
   DB_PORT=5432
   ```

4. **Crear la base de datos en PostgreSQL**:
   Asegúrese de crear la base de datos `programacion1_db` en su servidor de PostgreSQL antes de continuar.

5. **Ejecutar migraciones**:
   ```bash
   python manage.py migrate
   ```

6. **Crear superusuario (Administrador)**:
   ```bash
   python manage.py createsuperuser
   ```

---

### 3. Configuración del Frontend (React + Vite)

1. NAVEGAR a la carpeta `frontend`:
   ```bash
   cd frontend
   ```

2. Instalar las dependencias de Node:
   ```bash
   npm install
   ```

---

## ▶️ Ejecución

Para ejecutar la aplicación completa en entorno de desarrollo:

### 🐍 Iniciar Servidor Backend (Django)
Desde la raíz del proyecto (con el entorno virtual activado):
```bash
python manage.py runserver
```
- **Servidor API**: `http://127.0.0.1:8000/`
- **Documentación Swagger UI**: `http://127.0.0.1:8000/api/docs/`
- **Esquema OpenAPI (JSON)**: `http://127.0.0.1:8000/api/schema/`
- **Panel Administrador Django**: `http://127.0.0.1:8000/admin/`

### ⚡ Iniciar Servidor Frontend (React)
Desde el directorio `frontend/`:
```bash
npm run dev
```
- **Aplicación Web**: `http://localhost:3000/`

## 🚀 Despliegue TP10 (configuración)

### Backend en Railway

1. Crear un servicio PostgreSQL y un servicio para este repositorio. En el servicio Django, Railway detecta `requirements.txt` e instala sus dependencias con Railpack.
2. En **Settings → Build**, establecer **Build Command** en:
   ```bash
   python manage.py collectstatic --noinput
   ```
3. En **Settings → Deploy**, establecer **Start Command** en:
   ```bash
   gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
   ```
   El `Procfile` de la raíz conserva el mismo comando. Configurar el comando explícitamente evita el inicio automático de Django de Railpack, que ejecutaría migraciones en cada arranque.
4. En **Pre-deploy Command**, establecer:
   ```bash
   python manage.py migrate --noinput
   ```
   Railway lo ejecuta antes de activar la nueva versión, en un contenedor separado con las variables de entorno y conectividad privada. Las migraciones modifican la base de datos, no necesitan persistir archivos del contenedor.
5. Configurar en el servicio Django, sin guardar secretos en el repositorio:
   - `DATABASE_URL`: referencia a la URL del servicio PostgreSQL.
   - `SECRET_KEY`: clave nueva, privada y distinta de cualquier clave local.
   - `DEBUG=false`.
   - `ALLOWED_HOSTS`: dominio público de la API, sin `https://`.
   - `CORS_ALLOWED_ORIGINS`: origen HTTPS de Vercel, sin barra final.
   - `SECURE_HSTS_SECONDS=0`, `SECURE_HSTS_INCLUDE_SUBDOMAINS=false` y `SECURE_HSTS_PRELOAD=false` para mantener HSTS desactivado inicialmente. Las cookies de sesión y CSRF se marcan Secure automáticamente cuando `DEBUG=false`.
   Railway proporciona `PORT`. El health check puede usar `/api/health/`; es una comprobación de proceso y no valida conectividad con PostgreSQL.
6. Después de la primera migración, crear el administrador desde el entorno del servicio Django con `python manage.py createsuperuser`.

Los comandos de build, start y pre-deploy se configuran en Railway, no en `railway.json`: la documentación vigente marca Config as Code como obsoleto y anuncia que los archivos existentes dejarán de funcionar el 1 de diciembre de 2026. No dejar el inicio Django automático, ya que el comando predeterminado de Railpack incluye `migrate`.

No se configura `SECURE_PROXY_SSL_HEADER` ni `SECURE_SSL_REDIRECT` hasta confirmar el encabezado HTTPS enviado por el proxy de Railway. Mantener HSTS en cero hasta verificar el HTTPS del dominio; no habilitar subdominios ni preload por defecto.

### Frontend en Vercel

Crear el proyecto con **Root Directory** `frontend/`, **Build Command** `npm run build` y **Output Directory** `dist`. Definir `VITE_API_URL` con la URL HTTPS pública de Railway en los entornos de producción y preview que se prueben. `frontend/vercel.json` reescribe las rutas de cliente a la aplicación para que React Router funcione al recargar o abrir una ruta directamente.

### Pendientes antes de producción

- Las fotos se almacenan actualmente en el filesystem local; no usar subidas de imágenes en Railway hasta integrar Cloudinary o almacenamiento persistente.
- El frontend debe apuntar al dominio de API correcto y el origen de Vercel debe estar permitido por CORS; actualizar CORS si se utiliza un dominio personalizado o previews.
- Verificar endpoints públicos y protegidos, login/refresh JWT, panel de administración, subidas de fotos una vez configuradas, y capturar evidencias del health check y de flujos principales para el TP.

---

## 🧪 Tests

### Backend (Django)

Crear y activar el entorno virtual e instalar las dependencias desde la raíz del proyecto:

```bash
# Windows (PowerShell)
py -m venv venv
.\venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

Ejecutar la suite completa (usa `config/test_settings.py`, con SQLite en memoria; no requiere PostgreSQL):

```bash
python manage.py test core users --settings=config.test_settings
```

### Frontend (React)

Desde el directorio `frontend/`, después de instalar las dependencias con `npm install`:

```bash
npm test          # tests en Node (node --test "tests/*.test.mjs")
npm run test:ui   # tests de componentes con Vitest (vitest run)
npm run lint      # linter (eslint .)
```

---

## 🗺️ Próximos pasos

- [ ] **Integración de API REST con Frontend**: Conectar los formularios de reserva (`Agendar.jsx`) y la vista de turnos (`MisTurnos.jsx`) a la API de Django mediante peticiones HTTP (Axios / Fetch) con tokens JWT.
- [ ] **Persistencia de Sesión JWT**: Almacenar y renovar de forma segura el token JWT en el cliente frontend.
- [ ] **Panel de Administración interactivo en React**: Permitir la cancelación/confirmación de turnos y la gestión dinámica del catálogo de servicios desde la vista `/admin`.
- [ ] **Selector dinámico de turnos**: Filtrar las horas disponibles en tiempo real según la duración del servicio seleccionado.
- [ ] **Completar despliegue TP10**: Configurar Railway y Vercel, resolver almacenamiento de imágenes y realizar pruebas de producción (ver sección de despliegue).

---

## 🎨 Diagrama de Diseño Inicial

El esquema inicial de la interfaz y estructura general de la aplicación se encuentra disponible en:
- **Diagrama versionado:** [docs/diagrama-diseno.md](docs/diagrama-diseno.md)
- [Diagrama en Google Drive](https://drive.google.com/file/d/19cnAAHszI8-OzWzl4cwZVv5lq9__dYfW/view?usp=sharing)

---

## 🎓 Contexto académico

Este proyecto se desarrolla como trabajo práctico integrador para la materia **Programación 1** de la carrera de **Ingeniería en Informática** de la **Universidad de Mendoza**.

---

## 👩‍💻 Autora

**Agustina Chamorro**  
Estudiante de Ingeniería en Informática — *Universidad de Mendoza*
