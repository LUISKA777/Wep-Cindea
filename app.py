from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
import os
import requests as http
from datetime import date, timedelta, datetime, time
import pytz

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'cindea-secret-key-12345')

CR_TZ = pytz.timezone('America/Costa_Rica')

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://cdhwvbbbboqkxzichrxt.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNkaHd2YmJiYm9xa3h6aWNocnh0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTAzNTAxOSwiZXhwIjoyMDk0NjExMDE5fQ.JBYZbzsbe7cAAxwZ6oUDW-XFUmpt0makEPmx5kNFz2A')

HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation'
}

def format_date_spanish(date_str):
    if not date_str:
        return ""
    # date_str is usually 'YYYY-MM-DD'
    from datetime import datetime
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        days = [
            "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"
        ]
        months = [
            "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
        ]
        return f"{days[dt.weekday()]}, {dt.day} de {months[dt.month-1]} de {dt.year}"
    except Exception:
        return date_str

def sb_get(table, params=''):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    try:
        r = http.get(url, headers=HEADERS)
        if r.status_code >= 400:
            print(f"Supabase Get Error {r.status_code}: {r.text}")
            return {'error': r.status_code, 'text': r.text}
        return r.json()
    except Exception as e:
        print(f"HTTP Request Exception: {e}")
        return {'error': 'EXCEPTION', 'text': str(e)}

def sb_post(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = http.post(url, json=data, headers=HEADERS)
    if r.status_code >= 400:
        print(f"Supabase Post Error {r.status_code}: {r.text}")
    return r.json()

def sb_patch(table, match_col, match_val, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{match_col}=eq.{match_val}"
    r = http.patch(url, json=data, headers=HEADERS)
    if r.status_code >= 400:
        print(f"Supabase Patch Error {r.status_code}: {r.text}")
    return r

def sb_delete(table, match_col, match_val):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{match_col}=eq.{match_val}"
    # Custom headers for delete to avoid potential 'return=representation' issues
    delete_headers = HEADERS.copy()
    delete_headers['Prefer'] = 'return=minimal'
    r = http.delete(url, headers=delete_headers)
    return r


class User(UserMixin):
    def __init__(self, user_id, username):
        self.id = user_id
        self.username = username

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'

@login_manager.user_loader
def load_user(user_id):
    data = sb_get('users', f'id=eq.{user_id}&select=*')
    if data and len(data) > 0:
        return User(user_id=data[0]['id'], username=data[0]['username'])
    return None

def get_vacancies_left(course):
    val = course['total_vacancies'] - course['filled_vacancies']
    course['vacancies_left_val'] = val
    course['vacancies_left'] = val
    return course

@app.route('/')
def index():
    courses = sb_get('courses', 'select=*')
    if not isinstance(courses, list):
        courses = []

    today_str = datetime.now(CR_TZ).date().isoformat()

    for c in courses:
        get_vacancies_left(c)
        # Check if course is closed
        closing_date = c.get('closing_date')
        if closing_date and today_str > closing_date:
            c['is_closed'] = True
        else:
            c['is_closed'] = False

    return render_template('index.html', courses=courses)

@app.route('/posts')
def posts():
    res = sb_get('posts', 'select=*&order=created_at.desc')
    if isinstance(res, dict) and 'error' in res:
        return f"Error de Supabase ({res['error']}): {res['text']}", 500
    if not isinstance(res, list):
        res = []
    return render_template('posts.html', posts=res)

@app.route('/post/<int:post_id>')
def post_detail(post_id):
    res = sb_get('posts', f'id=eq.{post_id}&select=*')
    if isinstance(res, dict) and 'error' in res:
        return f"Error de Supabase ({res['error']}): {res['text']}", 500
    if not res or len(res) == 0:
        return "Post no encontrado", 404
    post = res[0]
    return render_template('post_detail.html', post=post)

@app.route('/enroll/<int:course_id>', methods=['GET', 'POST'])
def enroll(course_id):
    data = sb_get('courses', f'id=eq.{course_id}&select=*')
    if not data or len(data) == 0:
        return "Curso no encontrado", 404
    course = data[0]
    get_vacancies_left(course)

    # Check if course is closed by date
    today_str = datetime.now(CR_TZ).date().isoformat()
    closing_date = course.get('closing_date')
    if closing_date and today_str > closing_date:
        flash('Lo sentimos, el periodo de inscripción para este curso ha finalizado.', 'danger')
        return redirect(url_for('index'))

    if course['vacancies_left'] <= 0:
        flash('Lo sentimos, este curso ya no tiene cupos disponibles.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form.get('name')
        cedula = request.form.get('cedula')
        phone = request.form.get('phone')
        if not name or not cedula or not phone:
            flash('Por favor complete todos los campos.', 'warning')
            return render_template('enroll.html', course=course)
        return redirect(url_for('schedule_appointment', course_id=course_id, name=name, cedula=cedula, phone=phone))

    return render_template('enroll.html', course=course)

@app.route('/schedule/<int:course_id>/<name>/<cedula>/<phone>', methods=['GET', 'POST'])
def schedule_appointment(course_id, name, cedula, phone):
    data = sb_get('courses', f'id=eq.{course_id}&select=*')
    if not data or len(data) == 0:
        return "Curso no encontrado", 404
    course = data[0]

    # Get global settings
    global_settings_data = sb_get('settings', 'select=*')
    global_s = global_settings_data[0] if (isinstance(global_settings_data, list) and len(global_settings_data) > 0) else {}

    # Get course-specific settings with defaults
    s = {
        'work_days': course.get('work_days') or global_s.get('work_days') or '0,1,2,3,4',
        'start_time': course.get('start_time') or global_s.get('start_time') or '08:00',
        'end_time': course.get('end_time') or global_s.get('end_time') or '16:00',
        'lunch_start': course.get('lunch_start') or global_s.get('lunch_start') or '12:00',
        'lunch_end': course.get('lunch_end') or global_s.get('lunch_end') or '13:00',
        'apt_duration': course.get('apt_duration') or global_s.get('apt_duration') or '60'
    }

    now_cr = datetime.now(CR_TZ)
    today = now_cr.date()
    current_time_str = now_cr.strftime('%H:%M')
    vacancies_left = course['total_vacancies'] - course['filled_vacancies']

    # Determine start date for slot generation
    opening_date_str = course.get('opening_date')
    global_opening_date_str = global_s.get('global_opening_date')

    start_date = today
    if opening_date_str:
        try:
            start_date = max(start_date, datetime.strptime(opening_date_str, '%Y-%m-%d').date())
        except ValueError:
            pass
    if global_opening_date_str:
        try:
            start_date = max(start_date, datetime.strptime(global_opening_date_str, '%Y-%m-%d').date())
        except ValueError:
            pass

    effective_start_date = start_date

    # Determine end date for slot generation
    closing_date_str = course.get('closing_date')
    global_closing_date_str = global_s.get('global_closing_date')

    effective_end_date = None
    if closing_date_str:
        try:
            effective_end_date = datetime.strptime(closing_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    if global_closing_date_str:
        try:
            g_closing = datetime.strptime(global_closing_date_str, '%Y-%m-%d').date()
            if effective_end_date is None or g_closing < effective_end_date:
                effective_end_date = g_closing
        except ValueError:
            pass

    # Generate all possible slots
    manual_slots_raw = course.get('manual_slots')
    all_possible_slots = []

    if manual_slots_raw and manual_slots_raw.strip():
        lines = manual_slots_raw.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                parts = line.split(' ')
                if len(parts) < 2:
                    continue
                date_part, time_part = parts[0], parts[1]

                slot_datetime = datetime.combine(datetime.strptime(date_part, '%Y-%m-%d').date(), time(int(time_part.split(':')[0]), int(time_part.split(':')[1])), tzinfo=CR_TZ)

                # Validate against now and start date
                if slot_datetime <= now_cr or datetime.strptime(date_part, '%Y-%m-%d').date() < effective_start_date:
                    continue

                # Validate against end date
                if effective_end_date and datetime.strptime(date_part, '%Y-%m-%d').date() > effective_end_date:
                    continue

                all_possible_slots.append({
                    'date': date_part,
                    'time': time_part
                })
            except Exception as e:
                print(f"Error parsing manual slot line '{line}': {e}")
                continue
    else:
        work_days = [int(d) for d in s['work_days'].split(',')]
        start_h, start_m = map(int, s['start_time'].split(':'))
        end_h, end_m = map(int, s['end_time'].split(':'))
        lunch_start_h, lunch_start_m = map(int, s['lunch_start'].split(':'))
        lunch_end_h, lunch_end_m = map(int, s['lunch_end'].split(':'))
        duration = int(s['apt_duration'])

        start_total_min = start_h * 60 + start_m
        end_total_min = end_h * 60 + end_m
        lunch_start_total = lunch_start_h * 60 + lunch_start_m
        lunch_end_total = lunch_end_h * 60 + lunch_end_m

        for i in range(30): # Increased range to ensure we hit end_date if it's far
            d = effective_start_date + timedelta(days=i)

            # Stop if we've passed the effective end date
            if effective_end_date and d > effective_end_date:
                break

            if d.weekday() in work_days:
                current_total_min = start_total_min
                while current_total_min + duration <= end_total_min:
                    slot_end = current_total_min + duration
                    if not (slot_end <= lunch_start_total or current_total_min >= lunch_end_total):
                        current_total_min = lunch_end_total
                        continue

                    h, m = divmod(current_total_min, 60)
                    time_str = f"{h:02d}:{m:02d}"

                    slot_datetime = datetime.combine(d, time(h, m), tzinfo=CR_TZ)
                    if slot_datetime <= now_cr:
                        current_total_min += duration
                        continue

                    all_possible_slots.append({
                        'date': d.isoformat(),
                        'time': time_str
                    })
                    current_total_min += duration

    # Filter out occupied slots
    occupied_slots = sb_get('appointments', f'course_id=eq.{course_id}&select=appointment_date,appointment_time')
    taken_set = set()
    if isinstance(occupied_slots, list):
        for slot in occupied_slots:
            d_val = slot['appointment_date'].split('T')[0] if 'T' in slot['appointment_date'] else slot['appointment_date']
            taken_set.add((d_val, slot['appointment_time']))

    available_slots = [slot for slot in all_possible_slots if (slot['date'], slot['time']) not in taken_set]

    # LIMIT slots to vacancies_left
    selected_slots = available_slots[:vacancies_left]

    # Prepare data for template
    formatted_dates = []
    available_times = []

    all_selected_times = sorted(list(set(slot['time'] for slot in selected_slots)))
    available_times = all_selected_times

    unique_dates = sorted(list(set(slot['date'] for slot in selected_slots)))
    for d in unique_dates:
        formatted_dates.append({
            'value': d,
            'label': format_date_spanish(d)
        })

    fake_taken = []
    for slot in all_possible_slots:
        if slot not in selected_slots:
            fake_taken.append([slot['date'], slot['time']])
    for t in taken_set:
        fake_taken.append(list(t))

    if request.method == 'POST':
        apt_date = request.form.get('date')
        apt_time = request.form.get('time')
        if not apt_date or not apt_time:
            flash('Por favor seleccione una fecha y hora.', 'warning')
            return render_template('appointment.html', course=course, name=name, cedula=cedula, phone=phone, dates=formatted_dates, times=available_times, taken=fake_taken)

        # SERVER-SIDE VALIDATION
        try:
            # Convert selected slot to datetime
            selected_dt = datetime.combine(datetime.strptime(apt_date, '%Y-%m-%d').date(), time(int(apt_time.split(':')[0]), int(apt_time.split(':')[1])), tzinfo=CR_TZ)

            # 1. Prevent past appointments
            if selected_dt <= now_cr:
                flash('Lo sentimos, no puede programar una cita en el pasado.', 'danger')
                return render_template('appointment.html', course=course, name=name, cedula=cedula, phone=phone, dates=formatted_dates, times=available_times, taken=fake_taken)

            # 2. Validate against effective start and end dates
            selected_date_val = selected_dt.date()
            if selected_date_val < effective_start_date:
                flash('La fecha seleccionada es anterior a la fecha de apertura.', 'danger')
                return render_template('appointment.html', course=course, name=name, cedula=cedula, phone=phone, dates=formatted_dates, times=available_times, taken=fake_taken)
            if effective_end_date and selected_date_val > effective_end_date:
                flash('La fecha seleccionada es posterior a la fecha de cierre.', 'danger')
                return render_template('appointment.html', course=course, name=name, cedula=cedula, phone=phone, dates=formatted_dates, times=available_times, taken=fake_taken)

            # 3. Verify the slot was actually offered as available
            if not any(slot['date'] == apt_date and slot['time'] == apt_time for slot in selected_slots):
                flash('Lo sentimos, este horario ya no está disponible o no es válido.', 'danger')
                return render_template('appointment.html', course=course, name=name, cedula=cedula, phone=phone, dates=formatted_dates, times=available_times, taken=fake_taken)
        except Exception as e:
            flash('Error al validar la fecha y hora seleccionadas.', 'danger')
            return render_template('appointment.html', course=course, name=name, cedula=cedula, phone=phone, dates=formatted_dates, times=available_times, taken=fake_taken)

        apt_data = sb_post('appointments', {
            'student_name': name,
            'student_cedula': cedula,
            'student_phone': phone,
            'course_id': course_id,
            'appointment_date': apt_date,
            'appointment_time': apt_time
        })
        sb_patch('courses', 'id', course_id, {'filled_vacancies': course['filled_vacancies'] + 1})

        flash('¡Cita de matrícula programada con éxito!', 'success')

        apt_id = apt_data.get('id') if isinstance(apt_data, dict) else (apt_data[0].get('id') if isinstance(apt_data, list) and apt_data else None)
        if apt_id:
            return redirect(url_for('appointment_receipt', apt_id=apt_id))
        return redirect(url_for('index'))

    return render_template('appointment.html', course=course, name=name, cedula=cedula, phone=phone, dates=formatted_dates, times=available_times, taken=fake_taken)

@app.route('/appointment/receipt/<int:apt_id>')
def appointment_receipt(apt_id):
    apt = sb_get('appointments', f'id=eq.{apt_id}&select=*,courses(name)')
    if not apt or len(apt) == 0:
        return "Cita no encontrada", 404

    apt_details = apt[0]
    apt_details['course_name'] = apt_details.get('courses', {}).get('name', 'Unknown') if apt_details.get('courses') else 'Unknown'

    # Format dates for the receipt
    if 'appointment_date' in apt_details:
        apt_details['appointment_date'] = format_date_spanish(apt_details['appointment_date'].split('T')[0])

    return render_template('receipt.html', appointment=apt_details)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        data = sb_get('users', f'username=eq.{username}&password=eq.{password}&select=*')
        if data and len(data) > 0:
            user = User(user_id=data[0]['id'], username=data[0]['username'])
            login_user(user)
            return redirect(url_for('admin_dashboard'))
        flash('Credenciales incorrectas.', 'danger')
    return render_template('admin_login.html')

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for('admin_login'))

@app.route('/admin')
@login_required
def admin_dashboard():
    courses = sb_get('courses', 'select=*')
    if not isinstance(courses, list):
        courses = []
    for c in courses:
        get_vacancies_left(c)

    appointments = sb_get('appointments', 'select=*,courses(name)&order=created_at.desc')
    if not isinstance(appointments, list):
        appointments = []
    for a in appointments:
        a['course_name'] = a.get('courses', {}).get('name', 'Unknown') if a.get('courses') else 'Unknown'
        # Format dates for display
        if 'appointment_date' in a:
            a['appointment_date'] = format_date_spanish(a['appointment_date'].split('T')[0])
        if 'created_at' in a:
            a['created_at'] = a['created_at'].split('T')[0] + ' ' + a['created_at'].split('T')[1][:5] if 'T' in a['created_at'] else a['created_at']

    return render_template('admin_dash.html', courses=courses, appointments=appointments)

@app.route('/admin/course/add', methods=['POST'])
@login_required
def add_course():
    name = request.form.get('name')
    description = request.form.get('description')
    vacancies = request.form.get('vacancies')

    # Nuevas configuraciones de horario por curso
    work_days = request.form.get('work_days')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    lunch_start = request.form.get('lunch_start')
    lunch_end = request.form.get('lunch_end')
    apt_duration = request.form.get('apt_duration')
    manual_slots = request.form.get('manual_slots')
    closing_date = request.form.get('closing_date')

    if name and description and vacancies:
        res = sb_post('courses', {
            'name': name,
            'description': description,
            'total_vacancies': int(vacancies),
            'filled_vacancies': 0,
            'work_days': work_days,
            'start_time': start_time,
            'end_time': end_time,
            'lunch_start': lunch_start,
            'lunch_end': lunch_end,
            'apt_duration': apt_duration,
            'manual_slots': manual_slots,
            'opening_date': request.form.get('opening_date'),
            'closing_date': closing_date
        })
        if isinstance(res, list) or (isinstance(res, dict) and 'id' in res):
            flash('Curso agregado exitosamente.', 'success')
        else:
            flash(f'Error al agregar curso: {res}', 'danger')
    else:
        flash('Por favor complete todos los campos.', 'warning')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    if request.method == 'POST':
        settings_data = {
            'work_days': request.form.get('work_days'), # e.g. "1,2,3,4,5" (Mon-Fri)
            'start_time': request.form.get('start_time'), # "08:00"
            'end_time': request.form.get('end_time'), # "16:00"
            'lunch_start': request.form.get('lunch_start'), # "12:00"
            'lunch_end': request.form.get('lunch_end'), # "13:00"
            'apt_duration': request.form.get('apt_duration', '60'), # "60" minutes
            'global_opening_date': request.form.get('global_opening_date'),
            'global_closing_date': request.form.get('global_closing_date')
        }

        # Get existing settings safely
        current = sb_get('settings', 'select=*')
        if isinstance(current, list) and len(current) > 0:
            sb_patch('settings', 'id', current[0]['id'], settings_data)
        else:
            # If it's a new table or empty, we post.
            # Note: If table doesn't exist, this will still fail via API, but not crash the server
            sb_post('settings', settings_data)

        flash('Configuración actualizada exitosamente.', 'success')
        return redirect(url_for('admin_settings'))

    settings = sb_get('settings', 'select=*')
    s = settings[0] if (isinstance(settings, list) and len(settings) > 0) else {
        'work_days': '0,1,2,3,4',
        'start_time': '08:00',
        'end_time': '16:00',
        'lunch_start': '12:00',
        'lunch_end': '13:00',
        'apt_duration': '60'
    }
    return render_template('admin_settings.html', settings=s)

@app.route('/admin/course/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_course(id):
    data = sb_get('courses', f'id=eq.{id}&select=*')
    if not data or len(data) == 0:
        return "Curso no encontrado", 404
    course = data[0]

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        vacancies = request.form.get('vacancies')
        work_days = request.form.get('work_days')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        lunch_start = request.form.get('lunch_start')
        lunch_end = request.form.get('lunch_end')
        apt_duration = request.form.get('apt_duration')
        manual_slots = request.form.get('manual_slots')

        if name and description and vacancies:
            r = sb_patch('courses', 'id', id, {
                'name': name,
                'description': description,
                'total_vacancies': int(vacancies),
                'work_days': work_days,
                'start_time': start_time,
                'end_time': end_time,
                'lunch_start': lunch_start,
                'lunch_end': lunch_end,
                'apt_duration': apt_duration,
                'manual_slots': manual_slots,
                'opening_date': request.form.get('opening_date'),
                'closing_date': request.form.get('closing_date')
            })
            if r.status_code in [200, 204]:
                flash('Curso actualizado exitosamente.', 'success')
            else:
                flash(f'Error al actualizar curso: {r.text}', 'danger')
        else:
            flash('Por favor complete todos los campos obligatorios.', 'warning')
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_course.html', course=course)

@app.route('/admin/course/delete/<int:id>')
@login_required
def delete_course(id):
    # Primero eliminamos todas las citas asociadas al curso para evitar el error 409 (Conflict)
    sb_delete('appointments', 'course_id', id)

    r = sb_delete('courses', 'id', id)
    if r.status_code in [200, 204]:
        flash('Curso y sus citas relacionadas fueron eliminados.', 'success')
    elif r.status_code == 409:
        flash('No se puede eliminar el curso debido a dependencias en la base de datos.', 'danger')
    else:
        flash(f'Error al eliminar el curso: {r.status_code}', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/appointment/delete/<int:id>')
@login_required
def delete_appointment(id):
    r = sb_delete('appointments', 'id', id)
    if r.status_code in [200, 204]:
        flash('Cita procesada y eliminada.', 'success')
    else:
        flash(f'Error al procesar la cita: {r.status_code}', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/posts')
@login_required
def admin_posts():
    posts = sb_get('posts', 'select=*,order=created_at.desc')
    if not isinstance(posts, list):
        posts = []
    return render_template('admin_posts.html', posts=posts)

@app.route('/admin/posts/add', methods=['GET', 'POST'])
@login_required
def add_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        if title and content:
            res = sb_post('posts', {'title': title, 'content': content})
            if isinstance(res, list) or (isinstance(res, dict) and 'id' in res):
                flash('Post agregado exitosamente.', 'success')
            else:
                flash(f'Error al agregar post: {res}', 'danger')
        else:
            flash('Por favor complete todos los campos.', 'warning')
        return redirect(url_for('admin_posts'))
    return render_template('admin_post_edit.html', post=None)

@app.route('/admin/posts/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_post(id):
    data = sb_get('posts', f'id=eq.{id}&select=*')
    if not data or len(data) == 0:
        return "Post no encontrado", 404
    post = data[0]
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        if title and content:
            r = sb_patch('posts', 'id', id, {'title': title, 'content': content})
            if r.status_code in [200, 204]:
                flash('Post actualizado exitosamente.', 'success')
            else:
                flash(f'Error al actualizar post: {r.text}', 'danger')
        else:
            flash('Por favor complete todos los campos obligatorios.', 'warning')
        return redirect(url_for('admin_posts'))
    return render_template('admin_post_edit.html', post=post)

@app.route('/admin/posts/delete/<int:id>')
@login_required
def delete_post(id):
    r = sb_delete('posts', 'id', id)
    if r.status_code in [200, 204]:
        flash('Post eliminado exitosamente.', 'success')
    else:
        flash(f'Error al eliminar post: {r.status_code}', 'danger')
    return redirect(url_for('admin_posts'))

@app.route('/matriculas')
def matriculas():
    res = sb_get('enrollment_dates', 'select=*&order=level.asc')
    if isinstance(res, dict) and 'error' in res:
        return f"Error de Supabase ({res['error']}): {res['text']}", 500
    if not isinstance(res, list):
        res = []
    return render_template('matriculas.html', dates=res)

@app.route('/admin/matriculas', methods=['GET', 'POST'])
@login_required
def admin_matriculas():
    if request.method == 'POST':
        id = request.form.get('id')
        level = request.form.get('level')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        if id:
            # Update existing
            if level and start_date and end_date:
                r = sb_patch('enrollment_dates', 'id', id, {'level': level, 'start_date': start_date, 'end_date': end_date})
                if r.status_code in [200, 204]:
                    flash('Fecha actualizada exitosamente.', 'success')
                else:
                    flash(f'Error al actualizar fecha: {r.text}', 'danger')
            else:
                flash('Por favor complete todos los campos.', 'warning')
        else:
            # Add new
            if level and start_date and end_date:
                res = sb_post('enrollment_dates', {'level': level, 'start_date': start_date, 'end_date': end_date})
                if isinstance(res, list) or (isinstance(res, dict) and 'id' in res):
                    flash('Fecha de matrícula agregada exitosamente.', 'success')
                else:
                    flash(f'Error al agregar fecha: {res}', 'danger')
            else:
                flash('Por favor complete todos los campos.', 'warning')

        return redirect(url_for('admin_matriculas'))

    data = sb_get('enrollment_dates', 'select=*,order=level.asc')
    if not isinstance(data, list):
        data = []
    return render_template('admin_matriculas.html', dates=data)


handler = app

if __name__ == '__main__':
    app.run(debug=True)
