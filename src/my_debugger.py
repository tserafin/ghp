from ctypes import *
from my_debugger_defines import *

kernel32 = windll.kernel32


class debugger():
    def __init__(self):
        self.h_process = None
        self.pid = None
        self.debugger_active = False
        self.h_thread = None
        self.context = None
        self.exception = None
        self.exception_address = None
        self.breakpoints = {}

    def load(self, path_to_exe):

        # dwCreation flag determines how to create the process
        # set creation_flags = CREATE_NEW_CONSOLE if you want
        # to see the calculator GUI
        creation_flags = DEBUG_PROCESS

        # instantiate the structs
        startupinfo = STARTUPINFO()
        process_information = PROCESS_INFORMATION()

        # The following two options allow the started process
        # to be shown as a separate window. This also illustrates
        # how different settings in the STARTUPINFO struct can affect
        # the debuggee
        startupinfo.dwFlags = 0x1
        startupinfo.wShowWindow = 0x0

        # We then initialise the cb variable in the STARTUPINFO struct
        # which is just the size of the struct itself
        startupinfo.cb = sizeof(startupinfo)

        if kernel32.CreateProcessA(path_to_exe,
                                   None,
                                   None,
                                   None,
                                   None,
                                   creation_flags,
                                   None,
                                   None,
                                   byref(startupinfo), byref(process_information)):
            print "[*] We have successfully launched the process!"
            print "[*] PID: %d" % process_information.dwProcessId

            # Obtain a valid handle to the newly created process
            # and store it for future access
            self.h_process = self.open_process(process_information.dwProcessId)

        else:
            self.test_win_error()

    def open_process(self, pid):
        h_process = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        return h_process

    def attach(self, pid):
        self.h_process = self.open_process(pid)

        # Attempt to attach to process
        # If this fails we exit the call
        if kernel32.DebugActiveProcess(pid):
            self.debugger_active = True
            self.pid = int(pid)
        else:
            print "[*] Unable to attach to the process."
            self.test_win_error()

    def run(self):
        # Now we have to poll the debuggee for debugging events
        while self.debugger_active:
            self.get_debug_event()

    def get_debug_event(self):

        debug_event = DEBUG_EVENT()
        continue_status = DBG_CONTINUE

        if kernel32.WaitForDebugEvent(byref(debug_event), INFINITE):
            # Obtain thread and context information
            self.h_thread = self.open_thread(debug_event.dwThreadId)
            self.context = self.get_thread_context(h_thread=self.h_thread)

            print "Event Code: %d Thread ID: %d" %(debug_event.dwDebugEventCode, debug_event.dwThreadId)

            # If the event code is an exception, we want to examine it further.
            if debug_event.dwDebugEventCode == EXCEPTION_DEBUG_EVENT:
                # Obtain the exception code
                exception = debug_event.u.Exception.ExceptionRecord.ExceptionCode
                self.exception_address = debug_event.u.Exception.ExceptionRecord.ExceptionAddress

                if exception == EXCEPTION_ACCESS_VIOLATION:
                    print "Access Violation Detected."
                # If a breakpoint is detected, we call an internal handler
                elif exception == EXCEPTION_BREAKPOINT:
                    continue_status = self.exception_handler_breakpoint()
                elif exception == EXCEPTION_GUARD_PAGE:
                    print "Guard Page Access Detected."
                elif exception == EXCEPTION_SINGLE_STEP:
                    print "Single Stepping."

            # raw_input("Press a key to continue...")
            # self.debugger_active = False
            kernel32.ContinueDebugEvent(debug_event.dwProcessId,
                                           debug_event.dwThreadId,
                                           continue_status)

    def exception_handler_breakpoint(self):
        print "[*] Inside the breakpoint handler."
        print "Exception Address: 0x%08x" %self.exception_address
        return DBG_CONTINUE

    def detach(self):
        if kernel32.DebugActiveProcessStop(self.pid):
            print "[*] Finished debugging. Exiting..."
            return True
        else:
            print "There was an error"
            self.test_win_error()

    def test_win_error(self):
        if kernel32.GetLastError() != 0:
            raise WinError()

    def open_thread(self, thread_id):
        h_thread = kernel32.OpenThread(THREAD_ALL_ACCESS, None, thread_id)

        if h_thread is not None:
            return h_thread
        else:
            print "[*] Could not obtain a valid thread handle."
            return False

    def enumerate_threads(self):
        thread_entry = THREADENTRY32()
        thread_list = []
        h_snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, self.pid)

        if h_snapshot is not None:
            # You have to set the size of the struct
            # or  the call will fail
            thread_entry.dwSize = sizeof(thread_entry)
            success = kernel32.Thread32First(h_snapshot, byref(thread_entry))

            while success:
                if thread_entry.th32OwnerProcessID == self.pid:
                    thread_list.append(thread_entry.th32ThreadID)
                success = kernel32.Thread32Next(h_snapshot, byref(thread_entry))
            kernel32.CloseHandle(h_snapshot)
            return thread_list
        else:
            return False

    def get_thread_context(self, thread_id=None, h_thread=None):
        context = CONTEXT()
        context.ContextFlags = CONTEXT_FULL | CONTEXT_DEBUG_REGISTERS

        # Obtain a handle to the thread
        if not h_thread:
            h_thread = self.open_thread(thread_id)
        if kernel32.GetThreadContext(h_thread, byref(context)):
            kernel32.CloseHandle(h_thread)
            return context
        else:
            return False

    def read_process_memory(self, address, length):
        data = ""
        read_buf = create_string_buffer(length)
        count = c_ulong(0)

        if not kernel32.ReadProcessMemory(self.h_process, address, read_buf, length, byref(count)):
            return False
        else:
            data += read_buf.raw
            return data

    def write_process_memory(self, address, data):
        count = c_ulong(0)
        length = len(data)

        c_data = c_char_p(data[count.value:])

        if not kernel32.WriteProcessMemory(self.h_process, address, c_data, length, byref(count)):
            return False
        else:
            return True

    def bp_set(self, address):
        if not self.breakpoints.has_key(address):
            try:
                # store the original byte
                original_byte = self.read_process_memory(address, 1)

                # write the INT3 opcode
                self.write_process_memory(address, "\xCC")

                # register the breakpoint in our internal list
                self.breakpoints[address] = (original_byte)
            except:
                return False
        "print [*] Setting breakpoint at: 0x%08x" %address
        return True

    def func_resolve(self, dll, function):
        handle = kernel32.GetModuleHandleA(dll)
        address = kernel32.GetProcAddress(handle, function)

        kernel32.CloseHandle(handle)

        return address