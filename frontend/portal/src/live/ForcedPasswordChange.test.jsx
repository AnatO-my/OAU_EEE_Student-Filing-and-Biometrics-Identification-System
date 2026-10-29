import { render,screen,fireEvent,waitFor } from '@testing-library/react';
import { describe,it,expect,vi } from 'vitest';
import ForcedPasswordChange from './ForcedPasswordChange';
import { apiRequest } from '../api';
const refreshUser=vi.fn();
vi.mock('../api',()=>({apiRequest:vi.fn()}));
vi.mock('../auth/useAuth',()=>({useAuth:()=>({refreshUser})}));
describe('mandatory temporary password change',()=>{
 it('checks confirmation before changing and refreshes identity only after success',async()=>{
  apiRequest.mockResolvedValue({detail:'Password changed'});render(<ForcedPasswordChange/>);
  fireEvent.change(screen.getByLabelText('Temporary password'),{target:{value:'temporary-synthetic'}});
  fireEvent.change(screen.getByLabelText('New password'),{target:{value:'new-synthetic-password'}});
  fireEvent.change(screen.getByLabelText('Confirm new password'),{target:{value:'different'}});
  fireEvent.click(screen.getByRole('button'));
  expect(apiRequest).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('Confirm new password'),{target:{value:'new-synthetic-password'}});
  fireEvent.click(screen.getByRole('button'));
  await waitFor(()=>expect(refreshUser).toHaveBeenCalledTimes(1));
 });
});
