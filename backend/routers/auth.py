import random
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel
import jwt

from backend.database import get_db, Employee, OTPVerification
from backend.schemas import Token, OTPRequest, UserSignup, UserLogin, EmployeeRead, ManagerRead, PasswordChange
from backend.auth_utils import verify_password, get_password_hash, create_access_token, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    user = db.query(Employee).filter(Employee.email == email).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if user.account_status != "APPROVED":
        raise HTTPException(status_code=403, detail=f"Account is {user.account_status}")
    return user


from backend.email_service import send_otp_email

@router.post("/request-otp")
def request_otp(payload: OTPRequest, db: Session = Depends(get_db)):
    existing_user = db.query(Employee).filter(Employee.email == payload.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    otp_code = str(random.randint(100000, 999999))
    expires = datetime.utcnow() + timedelta(minutes=10)
    
    # Delete old OTPs for this email
    db.query(OTPVerification).filter(OTPVerification.email == payload.email).delete()
    
    new_otp = OTPVerification(email=payload.email, otp_code=otp_code, expires_at=expires)
    db.add(new_otp)
    db.commit()
    
    # Send actual email
    success = send_otp_email(to_email=payload.email, otp_code=otp_code)
    
    if not success:
        # We don't block registration if SMTP isn't set up yet, but we log it
        print("="*40)
        print(f"FALLBACK SIMULATED EMAIL TO {payload.email}")
        print(f"Your ExpenseOps OTP Code is: {otp_code}")
        print("="*40)
        return {"message": "OTP generated (simulated local delivery due to missing SMTP)"}
    
    return {"message": "OTP sent successfully to your email"}

from backend.schemas import PasswordResetConfirm

@router.post("/forgot-password")
def forgot_password(payload: OTPRequest, db: Session = Depends(get_db)):
    user = db.query(Employee).filter(Employee.email == payload.email).first()
    if not user:
        # To prevent email enumeration, we still return a success message
        return {"message": "If that email exists, an OTP has been sent."}
        
    otp_code = str(random.randint(100000, 999999))
    expires = datetime.utcnow() + timedelta(minutes=10)
    
    db.query(OTPVerification).filter(OTPVerification.email == payload.email).delete()
    
    new_otp = OTPVerification(email=payload.email, otp_code=otp_code, expires_at=expires)
    db.add(new_otp)
    db.commit()
    
    success = send_otp_email(to_email=payload.email, otp_code=otp_code)
    
    if not success:
        print("="*40)
        print(f"PASSWORD RESET SIMULATED EMAIL TO {payload.email}")
        print(f"Your ExpenseOps Password Reset OTP Code is: {otp_code}")
        print("="*40)
        return {"message": "If that email exists, an OTP has been sent. (Simulated)"}
    
    return {"message": "If that email exists, an OTP has been sent."}

@router.post("/reset-password")
def reset_password(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    otp_record = db.query(OTPVerification).filter(
        OTPVerification.email == payload.email,
        OTPVerification.otp_code == payload.otp_code
    ).first()
    
    if not otp_record or otp_record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
        
    user = db.query(Employee).filter(Employee.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.hashed_password = get_password_hash(payload.new_password)
    db.query(OTPVerification).filter(OTPVerification.email == payload.email).delete()
    db.commit()
    
    return {"message": "Password has been successfully reset."}
from backend.config import get_settings
settings = get_settings()

@router.post("/signup")
def signup(payload: UserSignup, db: Session = Depends(get_db)):
    if payload.role in ["CEO", "Director"]:
        if payload.master_key != settings.EXECUTIVE_MASTER_KEY:
            raise HTTPException(status_code=403, detail="Invalid Master Key for executive signup.")
        
    # Verify OTP
    otp_record = db.query(OTPVerification).filter(
        OTPVerification.email == payload.email,
        OTPVerification.otp_code == payload.otp_code
    ).first()
    
    if not otp_record or otp_record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
        
    db.query(OTPVerification).filter(OTPVerification.email == payload.email).delete()
    
    emp_id = f"EMP-{uuid.uuid4().hex[:8].upper()}"
    hashed_pwd = get_password_hash(payload.password)
    
    status_val = "PENDING_APPROVAL" if (payload.manager_id and payload.manager_id.strip()) else "APPROVED"
    
    new_employee = Employee(
        employee_id=emp_id,
        name=payload.name,
        email=payload.email,
        hashed_password=hashed_pwd,
        role=payload.role,
        department=payload.department,
        manager_id=payload.manager_id if (payload.manager_id and payload.manager_id.strip()) else None,
        account_status=status_val
    )
    
    db.add(new_employee)
    db.commit()
    db.refresh(new_employee)
    
    msg = "Signup successful. Waiting for manager approval." if status_val == "PENDING_APPROVAL" else "Signup successful. Your account is active."
    return {"message": msg, "status": status_val}

@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(Employee).filter(Employee.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
        
    if user.account_status != "APPROVED":
        if user.account_status == "PENDING_APPROVAL":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="your account is not authrized by your manager"
            )
        raise HTTPException(status_code=403, detail=f"Account is {user.account_status}")
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=EmployeeRead)
def get_me(current_user: Employee = Depends(get_current_user)):
    return current_user

@router.get("/managers", response_model=list[ManagerRead])
def get_managers(db: Session = Depends(get_db)):
    managers = db.query(Employee).filter(
        Employee.role.in_(["Manager", "Director", "VP", "CEO"]),
        Employee.account_status == "APPROVED"
    ).all()
    return managers

@router.put("/change-password")
def change_password(payload: PasswordChange, current_user: Employee = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect current password")
    
    current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {"status": "success", "message": "Password updated successfully"}

class EnvironmentSwitch(BaseModel):
    environment: str

@router.post("/environment")
def switch_environment(payload: EnvironmentSwitch, current_user: Employee = Depends(get_current_user)):
    if current_user.role != "CEO":
        raise HTTPException(status_code=403, detail="Only the CEO can switch environments.")
        
    env = payload.environment.lower()
    if env not in ["demo", "production"]:
        raise HTTPException(status_code=400, detail="Invalid environment specified.")
        
    import backend.database as db_module
    from backend.config import get_settings
    
    settings = get_settings()
    
    if env == "production" and not settings.SUPABASE_URL:
        raise HTTPException(status_code=400, detail="Production environment (Supabase) is not configured in .env")
        
    db_module.ACTIVE_ENV = env
    
    # If switching to production, ensure tables are created
    if env == "production" and db_module.postgres_engine:
        db_module.Base.metadata.create_all(bind=db_module.postgres_engine)
        
    return {"status": "success", "message": f"Successfully switched to {env} environment."}
