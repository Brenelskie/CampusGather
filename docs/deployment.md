# CampusGather hosting and group review

The [live CampusGather website](https://bren11.pythonanywhere.com/) runs the source from [Brenelskie/CampusGather](https://github.com/Brenelskie/CampusGather). The first deployment was verified on **13 November 2026**. CampusGather now uses the existing PythonAnywhere address that previously served Hangarin. The old Hangarin files, environment and private rollback backup are retained.

## For groupmates

1. Open the live website. You can read published and cancelled sample events without logging in.
2. Open an event to inspect its schedule, announcements, map and event-day weather.
3. Choose **Join CampusGather**, create a student account, then try registering for a future published event.
4. Open **My registrations** to view your registration, edit its note or cancel it.
5. Ask the project owner for organizer access if you need to review event creation and management. Public signup creates a student account.
6. To run and change the code yourself, clone the GitHub repository and follow the Windows commands in the README. Your local database and accounts are separate from the hosted site.

The server was initialized with five synthetic events: three published, one cancelled and one private draft. Visitors therefore see **four**, while the demo organizer can see its draft too. The seed also created one organization, two venues, two categories, five agenda items, five announcements and three sample registrations. These examples are not real campus activities or attendee records.

## Owner: create your private administrator

No administrator account or shared administrator password is seeded. The hosting owner enters this password privately.

1. Sign in to PythonAnywhere as **Bren11** and open a **Bash** console.
2. Run this command:

   ```bash
   /home/Bren11/.virtualenvs/campusgather-venv/bin/python /home/Bren11/CampusGather/manage.py createsuperuser
   ```

3. Choose your administrator username. Supply an email if desired, then enter and repeat a strong password. The terminal normally shows no characters while you type a password.
4. Open [CampusGather login](https://bren11.pythonanywhere.com/accounts/login/) and sign in using that account.
5. Open [Organizer access](https://bren11.pythonanywhere.com/accounts/roles/) to grant the **Organizers** group to your groupmates' accounts. Django administration is at [Admin](https://bren11.pythonanywhere.com/admin/).

The synthetic organizer username is `demo_organizer`; two synthetic students are `demo_student` and `demo_student2`. Their generated password is stored privately in the hosting account, not in GitHub or this guide. The seed does not reset existing passwords. If you deliberately change an account password, run `manage.py changepassword <username>` with this project's Python and type the new password privately.

## Current hosting configuration

| Setting | Value |
|---|---|
| Source and working directory | `/home/Bren11/CampusGather` |
| Python version | 3.13 |
| Virtual environment | `/home/Bren11/.virtualenvs/campusgather-venv` |
| Hosted WSGI entry point | `/var/www/bren11_pythonanywhere_com_wsgi.py` |
| Django settings module | `config.settings` |
| Static URL | `/static/` |
| Static directory | `/home/Bren11/CampusGather/staticfiles` |
| Database | Private server-only SQLite database in the project directory |

The server-only `.env` contains a newly generated secret key, `DJANGO_DEBUG=False`, the exact allowed hostname and the HTTPS trusted CSRF origin. The environment file has private file permissions and is excluded from Git. Secure session/CSRF cookies are enabled. PythonAnywhere's **Force HTTPS** setting redirects HTTP visitors to HTTPS.

The hosted WSGI file inserts the CampusGather project path into `sys.path`, sets `DJANGO_SETTINGS_MODULE` to `config.settings`, and calls `get_wsgi_application()`. Project settings load the private `.env` automatically. The public repository contains `.env.example` for local setup.

## Owner: publish later updates

Commit and push the intended source changes to GitHub first. Back up the server database privately before a change that modifies its schema or data. Keep the current database and `.env`; do not replace them with a groupmate's local copies.

Open a PythonAnywhere Bash console and run these commands one at a time:

```bash
cd /home/Bren11/CampusGather
git status --short
```

If tracked source files have local edits, resolve those edits before pulling. When the tracked tree is clean:

```bash
git pull --ff-only origin main
source /home/Bren11/.virtualenvs/campusgather-venv/bin/activate
python -m pip install -r requirements.txt
python manage.py check
python manage.py migrate --noinput
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
```

After all commands succeed, open PythonAnywhere **Web** and click **Reload Bren11.pythonanywhere.com**. Refresh the live site and test the feature you changed. If an error occurs, inspect the web app's error log; do not turn on public debug output or paste credentials into a report. Use a fast-forward pull so server changes are not silently overwritten.

## Renewal and external services

At deployment, the free website was reactivated until **13 December 2026**. Before its displayed expiry, sign in to PythonAnywhere, open **Web**, and click **Run until 1 month from today**. Read the displayed date after each renewal.

Maps require access to Leaflet and OpenStreetMap tiles. Weather requires Open-Meteo and an event date from today through fifteen days ahead. On the deployment run, a real November 18 forecast and map tiles loaded successfully. A date beyond that range intentionally shows an availability message. A provider outage can still happen; the app keeps event information and registration available and displays the reason it could not obtain a forecast.

The prior Hangarin database and WSGI entry point were backed up privately before the switch. Restoring Hangarin would require restoring its previous WSGI/source/working/virtualenv/static settings and reloading the web app; neither project's database needs to be deleted.

Hosting references: [PythonAnywhere Django deployment](https://help.pythonanywhere.com/pages/DeployExistingDjangoProject/) and [Django static files](https://help.pythonanywhere.com/pages/DjangoStaticFiles/).
