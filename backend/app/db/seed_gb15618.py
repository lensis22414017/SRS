"""预置领域种子: 因子字典(8重金属+通用) + GB15618-2018 国标阈值。幂等。"""
from sqlalchemy.orm import Session
from app.models import FactorDictionary, ThresholdRule

FACTORS = [
    ("pH","pH","化学性质","chemical",None),
    ("镉","镉","环境指标","pollutant","mg/kg"),
    ("铅","铅","环境指标","pollutant","mg/kg"),
    ("砷","砷","环境指标","pollutant","mg/kg"),
    ("铬","铬","环境指标","pollutant","mg/kg"),
    ("汞","汞","环境指标","pollutant","mg/kg"),
    ("铜","铜","环境指标","pollutant","mg/kg"),
    ("锌","锌","环境指标","pollutant","mg/kg"),
    ("镍","镍","环境指标","pollutant","mg/kg"),
    ("有机质","有机质","肥力指标","fertility","g/kg"),
    ("全氮","全氮","肥力指标","fertility","g/kg"),
    ("全磷","全磷","肥力指标","fertility","g/kg"),
    ("全钾","全钾","肥力指标","fertility","g/kg"),
]
GB = {
    "镉":[("pH<=5.5",0.3),("5.5<pH<=6.5",0.3),("6.5<pH<=7.5",0.3),("pH>7.5",0.6)],
    "汞":[("pH<=5.5",1.3),("5.5<pH<=6.5",1.8),("6.5<pH<=7.5",2.4),("pH>7.5",3.4)],
    "砷":[("pH<=5.5",40),("5.5<pH<=6.5",40),("6.5<pH<=7.5",30),("pH>7.5",25)],
    "铅":[("pH<=5.5",70),("5.5<pH<=6.5",90),("6.5<pH<=7.5",120),("pH>7.5",170)],
    "铬":[("pH<=5.5",150),("5.5<pH<=6.5",150),("6.5<pH<=7.5",200),("pH>7.5",250)],
    "铜":[("pH<=5.5",50),("5.5<pH<=6.5",50),("6.5<pH<=7.5",100),("pH>7.5",100)],
    "镍":[("pH<=5.5",60),("5.5<pH<=6.5",70),("6.5<pH<=7.5",100),("pH>7.5",190)],
    "锌":[("pH<=5.5",200),("5.5<pH<=6.5",200),("6.5<pH<=7.5",250),("pH>7.5",300)],
}

def seed_domain(db):
    existing = {fd.factor_code for fd in db.query(FactorDictionary).all()}
    fmap = {fd.factor_code: fd.id for fd in db.query(FactorDictionary).all()}
    nf=0
    for code,name,cat,ftype,unit in FACTORS:
        if code not in existing:
            fd=FactorDictionary(factor_code=code,factor_name=name,level1_category=cat,factor_type=ftype,default_unit=unit)
            db.add(fd); db.flush(); fmap[code]=fd.id; nf+=1
    er={(r.factor_id,r.land_type) for r in db.query(ThresholdRule).all()}
    nt=0
    for code,levels in GB.items():
        fid=fmap.get(code)
        if not fid: continue
        for ph,val in levels:
            if (fid,"农用地("+ph+")") in er: continue
            db.add(ThresholdRule(factor_id=fid,application_scenario="农用地土壤污染风险筛选",
                applicable_scope="production",land_type="农用地("+ph+")",
                threshold_min=None,threshold_max=float(val),unit="mg/kg",
                threshold_original=code+" "+ph+": <="+str(val)+" mg/kg",
                standard_source="GB15618-2018 表1 农用地土壤污染风险筛选值",version="V1.0"))
            nt+=1
    db.commit()
    print("因子字典新增",nf,"总",db.query(FactorDictionary).count(),"| GB15618阈值新增",nt,"总",db.query(ThresholdRule).count())

if __name__=="__main__":
    from app.db.session import SessionLocal
    seed_domain(SessionLocal())
