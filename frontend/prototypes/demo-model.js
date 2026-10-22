(function(root){
  'use strict';
  const students=[
    {id:'EEE/2022/001',name:'Adebayo Adeyemi',level:400,phone:'0800 000 0001',email:'adebayo@example.test',address:'Sample campus address',admission:'UTME',year:2022},
    {id:'EEE/2022/043',name:'Fatima Ibrahim',level:400,phone:'0800 000 0002',email:'fatima@example.test',address:'Sample campus address',admission:'UTME',year:2022},
    {id:'EEE/2021/014',name:'Chidinma Okafor',level:500,admission:'UTME',year:2021},
    {id:'EEE/2023/028',name:'Tomiwa Balogun',level:300,admission:'UTME',year:2023},
    {id:'EEE/2024/019',name:'Emeka Nwosu',level:200,admission:'UTME',year:2024},
    {id:'EEE/2025/007',name:'Zainab Bello',level:100,admission:'UTME',year:2025}
  ];
  const courses=[
    {code:'EEE401',title:'Control Systems',units:3,type:'Compulsory',level:400,semester:'Harmattan'},
    {code:'EEE403',title:'Electrical Machines',units:3,type:'Compulsory',level:400,semester:'Harmattan'},
    {code:'EEE405',title:'Communication Systems',units:3,type:'Compulsory',level:400,semester:'Harmattan'},
    {code:'EEE407',title:'Engineering Laboratory',units:2,type:'Compulsory',level:400,semester:'Harmattan'},
    {code:'EEE409',title:'Renewable Energy',units:3,type:'Elective',level:400,semester:'Harmattan'},
    {code:'EEE402',title:'Digital Signal Processing',units:3,type:'Compulsory',level:400,semester:'Rain'}
  ];
  const id=()=>globalThis.crypto?.randomUUID?.()||`demo-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  function seed(){return {version:3,students:structuredClone(students),courses:structuredClone(courses),
    assignments:[{id:'a1',kind:'Adviser',staff:'Dr. O. Demo',target:'400',active:true},{id:'a2',kind:'Lecturer',staff:'Dr. O. Demo',target:'EEE401',active:true},{id:'a3',kind:'Lecturer',staff:'Dr. O. Demo',target:'EEE403',active:true}],
    staffProfile:{name:'Dr. O. Demo',designation:'Senior lecturer',email:'staff@example.test',phone:'0800 000 0010',office:'Sample office E12'},
    registrations:[{id:'r1',student:students[0].id,session:'2026/2027',semester:'Harmattan',codes:['EEE401','EEE403','EEE405','EEE407'],status:'Draft',comment:''},{id:'r2',student:students[1].id,session:'2026/2027',semester:'Harmattan',codes:['EEE401','EEE403','EEE405','EEE407'],status:'Submitted',comment:''}],
    results:[{id:'g1',session:'2025/2026',semester:'Harmattan',course:'EEE401',status:'Approved',scores:{[students[0].id]:72,[students[1].id]:58},comment:'Synthetic historical result.'}],
    requests:[{id:'q1',student:students[1].id,category:'Profile correction',subject:'Review contact details',body:'Please confirm my contact details in the sample record.',status:'Submitted',attachment:'',responses:[],escalated:false}],
    appointments:[],notes:[],history:[],
    messages:[{id:'m1',sender:'HOD',subject:'Welcome to the new session',body:'Review your details and contact your part adviser about corrections.',recipients:students.map(s=>s.id).concat('staff','adviser'),date:'2026-10-06',read:[]}],
    notifications:[{id:'n1',recipient:students[0].id,title:'Registration deadline',body:'Demo deadline: 16 October 2026. Submit your selected courses for adviser review.',read:false}],
    resources:[{id:'f1',course:'EEE401',title:'Control systems study guide',filename:'control-systems-guide.txt',text:'OAU EEE — synthetic learning resource\n\nControl systems: review feedback, stability and block diagrams.\nThis demonstration file is not official course material.'}],
    timetable:[{id:'t1',course:'EEE401',kind:'Lecture',day:'Monday',time:'09:00–11:00',venue:'Sample room E1',note:''},{id:'t2',course:'EEE403',kind:'Lecture',day:'Wednesday',time:'11:00–13:00',venue:'Sample room E2',note:''},{id:'t3',course:'EEE401',kind:'Examination',day:'20 October 2026',time:'09:00–12:00',venue:'Sample exam hall',note:'Demonstration schedule only'}]
  };}
  const current='2026/2027';
  function studentIds(state,role){if(role==='student')return [students[0].id];if(role==='hod')return state.students.map(s=>s.id);if(role==='adviser'){const levels=state.assignments.filter(a=>a.kind==='Adviser'&&a.active&&a.staff==='Dr. O. Demo').map(a=>Number(a.target));return state.students.filter(s=>levels.includes(s.level)).map(s=>s.id);}return [];}
  function courseIds(state,role){if(role==='hod')return state.courses.map(c=>c.code);if(role==='student')return state.courses.filter(c=>c.level===state.students[0].level).map(c=>c.code);if(role==='adviser')return state.courses.filter(c=>state.assignments.some(a=>a.kind==='Adviser'&&a.active&&Number(a.target)===c.level)).map(c=>c.code);return state.assignments.filter(a=>a.kind==='Lecturer'&&a.active&&a.staff==='Dr. O. Demo').map(a=>a.target);}
  const ensure=(condition,message)=>{if(!condition)throw new Error(message);};
  function notify(state,recipient,title,body){state.notifications.unshift({id:id(),recipient,title,body,read:false});}
  function log(state,role,action,subject,comment=''){state.history.unshift({id:id(),actor:role==='student'?students[0].name:role==='hod'?'HOD Demo':'Dr. O. Demo',role,action,subject,comment,date:new Date().toISOString()});}
  function registration(state,student,session=current,semester='Harmattan'){return state.registrations.find(r=>r.student===student&&r.session===session&&r.semester===semester);}
  function apply(state,role,action,p={}){
    const ids=studentIds(state,role),courseScope=courseIds(state,role);
    if(action==='profile'){
      const person=role==='student'?state.students[0]:state.staffProfile;
      ensure(/^\S+@\S+\.\S+$/.test(p.email||''),'Enter a valid email address.');ensure((p.phone||'').trim().length>=7,'Enter a valid phone number.');
      Object.assign(person,{email:p.email.trim(),phone:p.phone.trim(),...(role==='student'?{address:p.address.trim()}:{office:p.office.trim()})});log(state,role,'Profile updated',person.name);return;
    }
    if(action==='saveRegistration'||action==='submitRegistration'){
      ensure(role==='student','Only the student may submit their registration.');const semester=p.semester||'Harmattan';let r=registration(state,students[0].id,current,semester);
      ensure(!r||['Draft','Returned for correction'].includes(r.status),'This registration is locked while submitted or approved.');
      const codes=[...new Set(p.codes||[])];ensure(codes.every(code=>state.courses.some(c=>c.code===code&&c.level===state.students[0].level&&c.semester===semester)),'Choose courses from the current level and semester.');
      if(action==='submitRegistration')ensure(codes.length>0,'Select at least one course before submitting.');
      if(!r){r={id:id(),student:students[0].id,session:current,semester,comment:''};state.registrations.push(r);}Object.assign(r,{codes,status:action==='submitRegistration'?'Submitted':'Draft'});log(state,role,action==='submitRegistration'?'Registration submitted':'Registration draft saved',r.id);
      if(action==='submitRegistration')notify(state,'adviser','Registration awaiting review',students[0].name+' submitted course selections.');return;
    }
    if(action==='registrationDecision'){
      const r=state.registrations.find(x=>x.id===p.id);ensure(role==='adviser'&&r&&ids.includes(r.student),'Only the assigned adviser may review this registration.');ensure(r.status==='Submitted','This registration is not awaiting review.');ensure(['Approved','Returned for correction'].includes(p.status),'Invalid decision.');ensure(p.status!=='Returned for correction'||p.comment?.trim(),'Explain what the student must correct.');r.status=p.status;r.comment=(p.comment||'').trim();log(state,role,p.status,r.id,r.comment);notify(state,r.student,'Registration '+p.status.toLowerCase(),r.comment||'Your course selections have been approved.');return;
    }
    if(action==='saveResult'||action==='submitResult'){
      ensure(['staff','hod'].includes(role)&&courseScope.includes(p.course),'Only the assigned lecturer or HOD may edit this course.');
      let r=state.results.find(x=>x.course===p.course&&x.session===current&&x.semester===p.semester);ensure(!r||['Draft','Returned for correction'].includes(r.status),'Submitted or approved results are locked.');
      const eligible=state.registrations.filter(x=>x.status==='Approved'&&x.session===current&&x.semester===p.semester&&x.codes.includes(p.course)).map(x=>x.student);
      ensure(Object.keys(p.scores).every(k=>eligible.includes(k)),'Score row is outside this course roster.');
      const scores={};for(const [key,value] of Object.entries(p.scores)){if(value===''){scores[key]=null;continue;}ensure(Number.isFinite(Number(value))&&Number(value)>=0&&Number(value)<=100,'Scores must be numbers from 0 to 100.');scores[key]=Number(value);}
      if(action==='submitResult')ensure(eligible.length>0&&eligible.every(k=>scores[k]!==null&&scores[k]!==undefined),'Enter a valid score for every enrolled student before submitting.');
      if(!r){r={id:id(),session:current,course:p.course,semester:p.semester,comment:''};state.results.push(r);}Object.assign(r,{scores,status:action==='submitResult'?'Submitted':'Draft'});log(state,role,r.status+' results',p.course);if(action==='submitResult')notify(state,'hod','Results awaiting approval',p.course+' results have been submitted.');return;
    }
    if(action==='resultDecision'){
      ensure(role==='hod','Only the HOD may approve results.');const r=state.results.find(x=>x.id===p.id);ensure(r&&r.status==='Submitted','This result is not awaiting approval.');ensure(['Approved','Returned for correction'].includes(p.status),'Invalid decision.');ensure(p.status==='Approved'||p.comment?.trim(),'Add a correction comment.');r.status=p.status;r.comment=(p.comment||'').trim();log(state,role,p.status+' results',r.course,r.comment);for(const sid of Object.keys(r.scores))notify(state,sid,'Results '+p.status.toLowerCase(),r.course+': '+(r.comment||'Your approved result is available.'));notify(state,'staff','Result decision',r.course+': '+p.status);return;
    }
    if(action==='request'){
      ensure(role==='student','Only students can create requests.');ensure(p.subject?.trim()&&p.body?.trim(),'Subject and request details are required.');
      state.requests.unshift({id:id(),student:students[0].id,category:p.category,subject:p.subject.trim(),body:p.body.trim(),attachment:p.attachment||'',status:'Submitted',responses:[],escalated:false});log(state,role,'Request submitted',p.subject);notify(state,'adviser','New student request',p.subject);return;
    }
    if(action==='respondRequest'||action==='escalate'){
      const q=state.requests.find(x=>x.id===p.id);ensure(q&&((role==='adviser'&&ids.includes(q.student))||role==='hod'||(role==='staff'&&q.category==='Course enquiry'&&courseScope.includes(q.course))),'This request is outside your permitted scope.');ensure(p.comment?.trim(),'Add a response or escalation reason.');
      if(action==='respondRequest')ensure(['In review','Resolved','Returned for correction',...(role==='hod'?['Approved']:[])].includes(p.status),'Choose a valid request status.');
      q.responses.push({actor:role==='hod'?'HOD':'Dr. O. Demo',body:p.comment.trim(),date:new Date().toISOString()});q.status=action==='escalate'?'Escalated to HOD':p.status||'In review';if(action==='escalate')q.escalated=true;log(state,role,q.status,q.subject,p.comment);notify(state,q.student,'Request update',q.subject+': '+q.status);if(action==='escalate')notify(state,'hod','Escalated request',q.subject);return;
    }
    if(action==='appointment'){
      ensure(role==='student','Only students can request an appointment.');ensure(p.date&&p.time&&p.reason?.trim(),'Date, time and reason are required.');ensure(p.date>='2026-10-06','Choose a date on or after 6 October 2026.');state.appointments.push({id:id(),student:students[0].id,date:p.date,time:p.time,reason:p.reason.trim(),status:'Requested',comment:''});notify(state,'adviser','Appointment requested',p.date+' '+p.time);return;
    }
    if(action==='appointmentDecision'){
      const a=state.appointments.find(x=>x.id===p.id);ensure(role==='adviser'&&a&&ids.includes(a.student),'Appointment is outside your assignment.');ensure(['Confirmed','Declined'].includes(p.status),'Choose a valid appointment decision.');a.status=p.status;a.comment=p.comment||'';notify(state,a.student,'Appointment '+p.status.toLowerCase(),a.date+' '+a.time+' '+a.comment);log(state,role,'Appointment '+p.status,a.id);return;
    }
    if(action==='note'){
      ensure(role==='adviser'&&ids.includes(p.student),'Only the assigned adviser may add notes.');ensure(p.body?.trim(),'Write a guidance note.');ensure(['Adviser and HOD only','Student and adviser'].includes(p.visibility),'Select note visibility.');state.notes.unshift({id:id(),student:p.student,body:p.body.trim(),followup:p.followup,visibility:p.visibility,date:new Date().toISOString()});log(state,role,'Advising note added',p.student);return;
    }
    if(action==='message'){
      ensure(role!=='student','Student communication uses requests.');ensure(p.subject?.trim()&&p.body?.trim(),'Subject and message are required.');let recipients=[];
      if(p.audience==='individual'){ensure(ids.includes(p.target),'Recipient is outside your student scope.');recipients=[p.target];}
      else if(p.audience==='level'){ensure(role==='hod'||role==='adviser','Only HOD or advisers may send cohort announcements.');recipients=state.students.filter(s=>s.level===Number(p.target)&&ids.includes(s.id)).map(s=>s.id);}
      else if(p.audience==='course'){ensure(courseScope.includes(p.target),'Course is outside your assignment.');recipients=[...new Set(state.registrations.filter(r=>r.session===current&&r.codes.includes(p.target)).map(r=>r.student))];}
      else if(p.audience==='adviser'){ensure(role==='hod','Only HOD may address advisers.');recipients=['adviser'];}
      ensure(recipients.length,'No recipients are available for this audience.');const message={id:id(),sender:role==='hod'?'HOD':'Dr. O. Demo',subject:p.subject.trim(),body:p.body.trim(),recipients,date:new Date().toISOString(),read:[]};state.messages.unshift(message);recipients.forEach(r=>notify(state,r,'New department message',message.subject));log(state,role,'Announcement sent',message.subject);return;
    }
    if(action==='assignment'){
      ensure(role==='hod','Only the HOD may manage assignments in this demo.');ensure(['Adviser','Lecturer'].includes(p.kind),'Invalid assignment type.');ensure(p.kind==='Adviser'?[100,200,300,400,500].includes(Number(p.target)):state.courses.some(c=>c.code===p.target),'Choose a valid target.');ensure(!state.assignments.some(a=>a.kind===p.kind&&a.target===p.target&&a.active),'An active assignment already exists.');state.assignments.push({id:id(),kind:p.kind,target:p.target,staff:'Dr. O. Demo',active:true});log(state,role,'Assignment created',p.kind+' '+p.target);return;
    }
    if(action==='toggleAssignment'){ensure(role==='hod','Only HOD may change assignments.');const a=state.assignments.find(x=>x.id===p.id);ensure(a,'Assignment not found.');a.active=!a.active;log(state,role,a.active?'Assignment activated':'Assignment deactivated',a.target);return;}
    if(action==='resource'){ensure(['staff','hod'].includes(role)&&courseScope.includes(p.course),'Only the assigned lecturer or HOD may upload resources.');ensure(p.title?.trim()&&p.filename,'Add a title and select a file.');state.resources.unshift({id:id(),course:p.course,title:p.title.trim(),filename:p.filename,text:p.text||'',local:true});state.registrations.filter(r=>r.codes.includes(p.course)&&r.session===current).forEach(r=>notify(state,r.student,'New course material',p.course+': '+p.title));log(state,role,'Resource uploaded',p.course);return;}
    if(action==='timetable'){ensure(role==='hod','Only HOD can publish schedule changes in this demo.');const t=state.timetable.find(x=>x.id===p.id);ensure(t&&p.venue?.trim()&&p.time?.trim(),'Venue and time are required.');Object.assign(t,{time:p.time.trim(),venue:p.venue.trim(),note:p.note||''});state.students.forEach(s=>notify(state,s.id,'Schedule changed',t.course+': '+t.time+' / '+t.venue));log(state,role,'Schedule changed',t.course,p.note);return;}
    throw new Error('Unknown demo action.');
  }
  function summary(state,student,session,semester){
    const rows=state.results.filter(r=>r.status==='Approved'&&r.session===session&&r.semester===semester&&r.scores[student]!=null).map(r=>{const course=state.courses.find(c=>c.code===r.course);const score=r.scores[student];const point=score>=70?5:score>=60?4:score>=50?3:score>=45?2:score>=40?1:0;return {code:r.course,title:course.title,units:course.units,score,grade:['F','E','D','C','B','A'][point],point};});
    const units=rows.reduce((n,r)=>n+r.units,0),gpa=units?(rows.reduce((n,r)=>n+r.units*r.point,0)/units).toFixed(2):null;
    const all=state.results.filter(r=>r.status==='Approved'&&r.scores[student]!=null);let points=0,total=0;all.forEach(r=>{const s=summaryScore(r.scores[student]),u=state.courses.find(c=>c.code===r.course).units;points+=s*u;total+=u;});
    return {rows,gpa,cgpa:total?(points/total).toFixed(2):null,outstanding:rows.filter(r=>r.score<40).map(r=>r.code)};
  }
  function summaryScore(score){return score>=70?5:score>=60?4:score>=50?3:score>=45?2:score>=40?1:0;}
  const api={seed,apply,studentIds,courseIds,registration,summary,current,id};if(typeof module!=='undefined')module.exports=api;else root.DemoModel=api;
})(typeof window!=='undefined'?window:globalThis);
