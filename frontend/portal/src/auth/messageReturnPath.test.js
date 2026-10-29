import { describe, expect, it } from 'vitest';
import { messageReturnPath } from './messageReturnPath';
const id = '12345678-1234-4234-8234-123456789abc';
describe('message notification return paths', () => {
  it('preserves the selected message while using the authenticated role', () => {
    expect(messageReturnPath('student', `/portal?section=messages&message=${id}`)).toBe(`/portal/student/messages?message=${id}`);
    expect(messageReturnPath('staff', `/portal/hod/messages?message=${id}`)).toBe(`/portal/staff/messages?message=${id}`);
  });
  it('rejects external destinations and unrelated private workspaces', () => {
    expect(messageReturnPath('student', `https://example.invalid/portal?section=messages&message=${id}`)).toBeNull();
    expect(messageReturnPath('student', '/portal/hod/account')).toBeNull();
  });
  it('drops malformed identifiers rather than interpolating arbitrary query data', () => {
    expect(messageReturnPath('student', '/portal?section=messages&message=../../account')).toBe('/portal/student/messages');
  });
});
