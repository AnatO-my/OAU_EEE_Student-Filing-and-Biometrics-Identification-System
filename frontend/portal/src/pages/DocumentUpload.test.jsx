import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import DocumentUpload from './DocumentUpload';
import { uploadStudentDocument } from '../api';

vi.mock('../api', () => ({ uploadStudentDocument: vi.fn() }));
describe('document upload', () => {
  it('requires replacement review and shows the server quality decision', async () => {
    uploadStudentDocument.mockResolvedValue({ original_filename: 'scan.pdf', status: 'needs_review', quality_notes: 'Manual review required.' });
    render(<DocumentUpload studentId="student-a" />);
    const file = new File(['%PDF-'], 'scan.pdf', { type: 'application/pdf' });
    fireEvent.change(screen.getByLabelText('Scanned document'), { target: { files: [file] } });
    expect(screen.getByRole('button', { name: 'Upload document' }).disabled).toBe(true);
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Upload document' }));
    expect((await screen.findByRole('status')).textContent).toContain('Needs review');
    expect(uploadStudentDocument).toHaveBeenCalledWith('student-a', file, 'result');
  });
});
