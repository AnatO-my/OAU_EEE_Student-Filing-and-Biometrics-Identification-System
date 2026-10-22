import { getGuardianSharingPreferences, getResultShare, listAcademicSessions, listGuardians, listResultShares, listStudents, previewGuardianResults, queueResultShare, retryFailedResultShares, setGuardianSharingPreferences } from '../api';

async function catalog(load) {
  const rows = [];
  for (let page = 1; page <= 100; page += 1) {
    const data = await load(page);
    rows.push(...data.results);
    if (!data.next) return rows;
  }
  throw new Error('The catalog is too large. Contact your administrator.');
}

// Reuse the portal's session/CSRF transport for the existing reviewed email workflow.
export const guardianClient = {
  sessions: () => catalog(page => listAcademicSessions(page)),
  students: filters => listStudents(filters),
  guardians: studentId => catalog(page => listGuardians(studentId, page)),
  preference: getGuardianSharingPreferences,
  savePreference: setGuardianSharingPreferences,
  preview: previewGuardianResults,
  batch: getResultShare,
  send: batch => queueResultShare(batch.id, batch.history_digest),
  retry: retryFailedResultShares,
  history: listResultShares,
};
