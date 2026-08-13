# 🚀 Render Deployment Checklist

## Pre-Deployment

- [x] ✅ Fixed `requirements.txt` (added gunicorn, psycopg2-binary)
- [ ] Commit changes to Git
- [ ] Push to GitHub
- [ ] Backup local database (if migrating data)

## Render Setup

### 1. Create PostgreSQL Database
- [ ] Go to Render Dashboard
- [ ] Click "New +" → "PostgreSQL"
- [ ] Name: `runrush-db`
- [ ] Region: Choose closest to your users
- [ ] Plan: Free or Starter
- [ ] Click "Create Database"
- [ ] **Copy Internal Database URL** (starts with `postgresql://`)

### 2. Create Web Service
- [ ] Click "New +" → "Web Service"
- [ ] Connect your GitHub repository
- [ ] Name: `runrush`
- [ ] Region: Same as database
- [ ] Branch: `main`
- [ ] Root Directory: Leave blank
- [ ] Runtime: Python 3
- [ ] Build Command: `pip install -r requirements.txt`
- [ ] Start Command: `gunicorn app:app`
- [ ] Plan: Free or Starter

### 3. Set Environment Variables
In the Render dashboard, add these environment variables:

#### Required
- [ ] `DATABASE_URL` = `<Internal Database URL from step 1>`
- [ ] `FLASK_ENV` = `production`
- [ ] `SECRET_KEY` = `<generate with command below>`

#### Optional
- [ ] `ADMIN_USER_ID` = `1`
- [ ] `RESEND_API_KEY` = `<your Resend API key>`
- [ ] `RESEND_FROM_EMAIL` = `RunRush <noreply@yourdomain.com>`

**Generate SECRET_KEY**:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Deploy
- [ ] Click "Create Web Service"
- [ ] Wait for build to complete (~2-5 minutes)
- [ ] Check logs for errors

## Post-Deployment

### 1. Verify Deployment
- [ ] Visit your app URL: `https://your-app.onrender.com`
- [ ] Check that landing page loads
- [ ] Try registering a new user
- [ ] Try logging in
- [ ] Test creating a run

### 2. Migrate Existing Data (if applicable)
If you have existing data in SQLite:

- [ ] Run migration script locally:
  ```bash
  export DATABASE_URL=<your Render PostgreSQL URL>
  python migrate_to_pg.py
  ```

### 3. Create Admin User
- [ ] Use Render Shell (in dashboard)
- [ ] Run: `flask create-admin`
- [ ] Or manually promote a user:
  ```sql
  UPDATE users SET role = 'admin' WHERE username = 'your_username';
  ```

### 4. Test All Features
- [ ] User registration
- [ ] User login
- [ ] Add run
- [ ] Edit run
- [ ] Delete run
- [ ] Social feed
- [ ] Leaderboard
- [ ] Admin panel (if admin)
- [ ] Offline sync
- [ ] Settings page

## Monitoring

### 1. Check Logs
- [ ] Go to Render dashboard
- [ ] Click on your service
- [ ] Click "Logs" tab
- [ ] Look for errors or warnings

### 2. Set Up Alerts (Optional)
- [ ] Configure email notifications in Render
- [ ] Set up uptime monitoring (e.g., UptimeRobot)
- [ ] Configure error tracking (e.g., Sentry)

## Troubleshooting

### Build Fails
**Error**: `gunicorn: command not found`
- ✅ **Fixed**: Added gunicorn to requirements.txt

**Error**: `No module named 'psycopg2'`
- ✅ **Fixed**: Added psycopg2-binary to requirements.txt

**Error**: `pip install failed`
- Check requirements.txt syntax
- Ensure all package versions are valid

### Deployment Fails
**Error**: `Application failed to start`
- Check logs in Render dashboard
- Verify start command: `gunicorn app:app`
- Check that app.py exists

**Error**: `Database connection failed`
- Verify DATABASE_URL is set correctly
- Check that PostgreSQL database is running
- Ensure Internal Database URL is used (not External)

### Runtime Errors
**Error**: `SECRET_KEY must be set`
- Set SECRET_KEY environment variable
- Generate with: `python -c "import secrets; print(secrets.token_hex(32))"`

**Error**: `Table does not exist`
- Database not initialized
- Check that `init_db()` runs on startup
- Manually run: `flask init-db` in Render Shell

## Performance Optimization

### 1. Enable Auto-Deploy
- [ ] In Render dashboard, enable "Auto-Deploy"
- [ ] Pushes to main branch will auto-deploy

### 2. Configure Health Checks
- [ ] Add health check path: `/health` (if implemented)
- [ ] Set health check interval

### 3. Scale (if needed)
- [ ] Upgrade to paid plan for more resources
- [ ] Add more instances for high traffic
- [ ] Consider adding Redis for rate limiting

## Security Checklist

- [ ] SECRET_KEY is set and secure (32+ characters)
- [ ] DATABASE_URL uses Internal URL (not External)
- [ ] FLASK_ENV is set to `production`
- [ ] HTTPS is enabled (automatic on Render)
- [ ] Environment variables are not in code
- [ ] .env file is in .gitignore

## Maintenance

### Regular Tasks
- [ ] Monitor error logs weekly
- [ ] Check database size monthly
- [ ] Update dependencies quarterly
- [ ] Backup database regularly
- [ ] Review security settings

### Updates
When updating code:
1. Test locally first
2. Push to GitHub
3. Render auto-deploys (if enabled)
4. Monitor logs for errors
5. Test critical features

## Rollback Plan

If deployment fails:

### Quick Rollback
1. Go to Render dashboard
2. Click "Manual Deploy"
3. Select previous successful commit
4. Click "Deploy"

### Full Rollback
1. Revert Git commit:
   ```bash
   git revert HEAD
   git push origin main
   ```
2. Render will auto-deploy previous version

## Success Criteria

- [ ] ✅ Build completes without errors
- [ ] ✅ Application starts successfully
- [ ] ✅ Landing page loads
- [ ] ✅ User can register
- [ ] ✅ User can login
- [ ] ✅ User can add runs
- [ ] ✅ Database persists data
- [ ] ✅ No errors in logs
- [ ] ✅ HTTPS works
- [ ] ✅ All features functional

## Next Steps

After successful deployment:

1. **Custom Domain** (Optional)
   - [ ] Add custom domain in Render
   - [ ] Update DNS records
   - [ ] Enable SSL certificate

2. **Monitoring**
   - [ ] Set up error tracking (Sentry)
   - [ ] Configure uptime monitoring
   - [ ] Set up performance monitoring

3. **Improvements**
   - [ ] Consider using improved version (app_new.py)
   - [ ] Add Redis for rate limiting
   - [ ] Implement API keys
   - [ ] Add more tests

## Resources

- **Render Docs**: https://render.com/docs
- **Flask Deployment**: https://flask.palletsprojects.com/en/latest/deploying/
- **Gunicorn Docs**: https://docs.gunicorn.org/
- **PostgreSQL Docs**: https://www.postgresql.org/docs/

## Support

- **Render Support**: https://render.com/docs/support
- **Community**: Render Community Forum
- **Status**: https://status.render.com/

---

## Quick Reference

### Render Dashboard URLs
- Dashboard: https://dashboard.render.com/
- Logs: Click service → Logs tab
- Shell: Click service → Shell tab
- Settings: Click service → Settings tab

### Common Commands (in Render Shell)
```bash
# Check Python version
python --version

# List installed packages
pip list

# Run Flask commands
flask --help
flask init-db
flask create-admin

# Check environment variables
env | grep FLASK
env | grep DATABASE
```

### Environment Variables Template
```
DATABASE_URL=postgresql://user:pass@host:5432/dbname
FLASK_ENV=production
SECRET_KEY=your-secret-key-here
ADMIN_USER_ID=1
RESEND_API_KEY=re_...
RESEND_FROM_EMAIL=RunRush <noreply@yourdomain.com>
```

---

**Deployment Status**: 🟡 In Progress  
**Last Updated**: Now  
**Next Review**: After first successful deployment

---

## 🎉 Completion

When all items are checked:
- [ ] Mark deployment as successful
- [ ] Document any issues encountered
- [ ] Share app URL with team
- [ ] Celebrate! 🎊

**Good luck with your deployment!** 🚀
