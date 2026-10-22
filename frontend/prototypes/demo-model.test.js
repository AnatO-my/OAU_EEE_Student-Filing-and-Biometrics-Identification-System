const test=require('node:test');
const assert=require('node:assert/strict');
const M=require('./demo-model.js');
const sid='EEE/2022/001',other='EEE/2022/043';
test('registration submission, return, correction and approval reach student notifications',()=>{
 const s=M.seed();M.apply(s,'student','submitRegistration',{codes:['EEE401','EEE403']});const r=M.registration(s,sid);
 assert.equal(r.status,'Submitted');assert.throws(()=>M.apply(s,'student','saveRegistration',{codes:['EEE401']}),/locked/);
 assert.throws(()=>M.apply(s,'adviser','registrationDecision',{id:r.id,status:'Returned for correction',comment:''}),/Explain/);
 M.apply(s,'adviser','registrationDecision',{id:r.id,status:'Returned for correction',comment:'Add laboratory.'});
 M.apply(s,'student','submitRegistration',{codes:['EEE401','EEE403','EEE407']});M.apply(s,'adviser','registrationDecision',{id:r.id,status:'Approved'});
 assert.equal(r.status,'Approved');assert.ok(s.notifications.some(n=>n.recipient===sid&&n.title==='Registration approved'));assert.equal(s.history.length,4);
});
test('scope revocation removes adviser reads and review authority',()=>{
 const s=M.seed();assert.equal(M.studentIds(s,'adviser').length,2);M.apply(s,'hod','toggleAssignment',{id:'a1'});assert.deepEqual(M.studentIds(s,'adviser'),[]);
 assert.throws(()=>M.apply(s,'adviser','registrationDecision',{id:'r2',status:'Approved'}),/assigned adviser/);
 assert.throws(()=>M.apply(s,'student','assignment',{kind:'Adviser',target:'400'}),/HOD/);
});
test('score validation, HOD return, resubmission, approval and derived results',()=>{
 const s=M.seed();s.registrations.forEach(r=>r.status='Approved');assert.throws(()=>M.apply(s,'staff','saveResult',{course:'EEE401',semester:'Harmattan',scores:{[sid]:101}}),/0 to 100/);
 assert.throws(()=>M.apply(s,'staff','submitResult',{course:'EEE401',semester:'Harmattan',scores:{[sid]:72,[other]:''}}),/every enrolled/);
 M.apply(s,'staff','saveResult',{course:'EEE401',semester:'Harmattan',scores:{[sid]:'',[other]:50}});assert.equal(M.summary(s,sid,M.current,'Harmattan').gpa,null);
 M.apply(s,'staff','submitResult',{course:'EEE401',semester:'Harmattan',scores:{[sid]:72,[other]:58}});const r=s.results.find(r=>r.session===M.current);
 assert.throws(()=>M.apply(s,'staff','resultDecision',{id:r.id,status:'Approved'}),/HOD/);
 M.apply(s,'hod','resultDecision',{id:r.id,status:'Returned for correction',comment:'Verify score.'});M.apply(s,'staff','submitResult',{course:'EEE401',semester:'Harmattan',scores:{[sid]:65,[other]:58}});M.apply(s,'hod','resultDecision',{id:r.id,status:'Approved'});
 assert.equal(M.summary(s,sid,M.current,'Harmattan').gpa,'4.00');assert.equal(M.summary(s,sid,M.current,'Harmattan').cgpa,'4.50');
 assert.throws(()=>M.apply(s,'staff','saveResult',{course:'EEE401',semester:'Harmattan',scores:{[sid]:100}}),/locked/);
});
test('request escalation and resolution notify the student and record decisions',()=>{
 const s=M.seed();M.apply(s,'student','request',{subject:'Academic concern',body:'Please review.',category:'Academic concern'});const q=s.requests[0];
 M.apply(s,'adviser','escalate',{id:q.id,comment:'Needs departmental review.'});assert.equal(q.status,'Escalated to HOD');
 M.apply(s,'hod','respondRequest',{id:q.id,status:'Resolved',comment:'Reviewed and resolved.'});assert.equal(q.responses.length,2);assert.ok(s.notifications.some(n=>n.recipient===sid&&n.body.includes('Resolved')));
});
test('messages retain recipient snapshots when assignment or level changes',()=>{
 const s=M.seed();M.apply(s,'adviser','message',{audience:'level',target:'400',subject:'Review',body:'Please review your files.'});const m=s.messages[0];s.students[0].level=500;assert.ok(m.recipients.includes(sid));
 assert.throws(()=>M.apply(s,'staff','message',{audience:'level',target:'400',subject:'Wrong scope',body:'No.'}),/HOD or advisers/);
 M.apply(s,'staff','message',{audience:'course',target:'EEE401',subject:'Class resource',body:'Available now.'});assert.ok(s.messages[0].recipients.includes(sid));
});
test('appointments, notes, uploads and schedules enforce role scope',()=>{
 const s=M.seed();M.apply(s,'student','appointment',{date:'2026-10-10',time:'10:00',reason:'Academic guidance'});M.apply(s,'adviser','appointmentDecision',{id:s.appointments[0].id,status:'Confirmed'});assert.equal(s.appointments[0].status,'Confirmed');
 M.apply(s,'adviser','note',{student:sid,body:'Guidance',visibility:'Student and adviser',followup:'2026-10-11'});assert.equal(s.notes.length,1);
 assert.throws(()=>M.apply(s,'staff','resource',{course:'EEE405',title:'File',filename:'guide.txt'}),/assigned lecturer/);
 M.apply(s,'staff','resource',{course:'EEE401',title:'File',filename:'guide.txt',text:'Demo guide'});assert.ok(s.notifications.some(n=>n.title==='New course material'));
 M.apply(s,'hod','timetable',{id:'t1',time:'10:00–12:00',venue:'E3',note:'Venue update'});assert.equal(s.timetable[0].venue,'E3');
});
