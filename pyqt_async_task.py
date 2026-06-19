#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
from typing import Any, Callable, Tuple, Type

from PyQt5.QtCore import QObject, QThread, QTimer, pyqtSignal

from log_util import log, current_thread_id


MsgIDThreadExit = 0
# QThread.wait() default timeout (ULONG_MAX); PyQt5 has no QThread.WaitForever.
_WAIT_FOREVER_MS = 0xFFFFFFFF
logfunc = log


class MyThread(QThread):
    Signal = pyqtSignal(tuple)

    def __init__(self, taskId: int, func: Callable[[pyqtSignal, int, Any], Any], args: Any, parent: QObject = None, notifyWhenExit: bool = True):
        super().__init__(parent)
        self.taskId = taskId
        self.func = func
        self.args = args
        self.notifyWhenExit = notifyWhenExit
        self.debugPrint = True

    def run(self) -> None:
        sysThreadId = current_thread_id()
        if self.debugPrint:
            logfunc('taskId {} runs in thread {}'.format(self.taskId, sysThreadId))
        result = self.func(self.Signal, self.taskId, self.args)
        if self.notifyWhenExit:
            self.Signal.emit((self.taskId, MsgIDThreadExit, result))


class AsyncTask():
    """
    A handy class to run a function in a separate thread and receive its result in the UI thread for PyQt5.
    """
    def __init__(self):
        super().__init__()
        self.taskThreads = {}
        self.taskNotifiers = {}
        self.taskId = 0
        self.msgIdName = {MsgIDThreadExit: 'MsgIDThreadExit'}
        self.delayCallTimer = QTimer()
        self.delayCallTimer.timeout.connect(self.onDelayCallTimer)
        self.delayCallFuncs = []
        self.delayCallMiniIntervalMs = 20
        self.debugPrint = True

    def setDelayCallMiniInterval(self, intervalMs: int = 20) -> None:
        self.delayCallMiniIntervalMs = intervalMs

    def delayCall(self, timeMs: int, func: Callable[[Any], None], *args, **kwargs) -> None:
        '''delay call func(*args, **kwargs) once after timeMs milliseconds'''
        assert timeMs > 0
        now = time.monotonic()
        self.delayCallFuncs.append([now + timeMs / 1000, 0, func, args, kwargs])
        self.delayCallTimer.start(self.delayCallMiniIntervalMs)

    def delayCall2(self, timeMs: int, intervalMs: int, func: Callable[[Any], None], *args, **kwargs) -> None:
        '''delay call func(*args, **kwargs) after timeMs milliseconds, if intervalMs is 0, call it once'''
        assert timeMs >= 0 and intervalMs >= 0
        now = time.monotonic()
        if timeMs == 0:
            func(*args, **kwargs)
        if timeMs or intervalMs:
            self.delayCallFuncs.append([now + timeMs / 1000, intervalMs, func, args, kwargs])
            self.delayCallTimer.start(self.delayCallMiniIntervalMs)

    def onDelayCallTimer(self) -> None:
        now = time.monotonic()
        index = 0
        while index < len(self.delayCallFuncs):
            future, intervalMs, func, args, kwargs = self.delayCallFuncs[index]
            if now >= future:
                #util.log(f'call {func} {args}')
                func(*args, **kwargs)
                if intervalMs == 0:
                    del self.delayCallFuncs[index]
                else:
                    self.delayCallFuncs[index][0] = future + intervalMs / 1000
                    index += 1
            else:
                index += 1
        if len(self.delayCallFuncs) == 0:
            self.delayCallTimer.stop()

    def setMsgIDName(self, msgId: int, name: str) -> None:
        assert msgId != 0, "can't use msgId 0, it is reserved for MsgIDThreadExit"
        self.msgIdName[msgId] = name

    def setMsgIDClass(self, msgIdClass: Type[Any]) -> None:
        for name, msgId in msgIdClass.__dict__.items():
            if not name.startswith("__"):
                if isinstance(msgId, int):
                    assert msgId != 0, "can't use msgId 0, it is reserved for MsgIDThreadExit"
                    self.msgIdName[msgId] = f'{msgIdClass.__name__}.{name}'

    def runTaskInThread(self, taskFunc: Callable[[pyqtSignal, int, Any], Any], args: Any, notifyFunc: Callable[[int, int, Any], None]) -> int:
        """
        Executes a given task in a new thread and provides a notification mechanism.

        The `notifyFunc` will be called in the caller's thread when the new thread emits
          a signal or when the task thread exits.

        Args:
            taskFunc (Callable[[pyqtSignal, int, Any], Any]):
                The function to be executed in the new thread. It must accept three arguments:
                - `signal` (pyqtSignal): A signal object to emit progress or results.
                - `taskId` (int): A unique ID assigned to the task.
                - `args` (Any): Arbitrary arguments passed to the task function.
                To notify the caller, `taskFunc` should call `signal.emit((taskId, msgId, data))`,
                where `msgId` must be greater than 0.

            args (Any):
                Arbitrary arguments to be passed directly to `taskFunc`.

            notifyFunc (Callable[[int, int, Any], None]):
                A function must accept `(taskId: int, msgId: int, data: Any)`.

        Returns:
            int: A unique task ID (starting from 1) corresponding to the newly created thread.
        """
        self.taskId += 1
        thread = MyThread(self.taskId, taskFunc, args)
        thread.debugPrint = self.debugPrint
        thread.Signal.connect(self._threadSlot)
        self.taskThreads[self.taskId] = thread
        self.taskNotifiers[self.taskId] = notifyFunc
        sysThreadId = current_thread_id()
        if self.debugPrint:
            logfunc('caller thread id {} spawns task id {}'.format(sysThreadId, self.taskId))
        thread.start()
        return self.taskId

    def waitTask(self, taskId: int, msecs: int = _WAIT_FOREVER_MS) -> bool:
        if taskId in self.taskThreads:
            return self.taskThreads[taskId].wait(msecs)
        return False

    def taskIsRunning(self) -> bool:
        return bool(self.taskThreads)

    def taskCount(self) -> int:
        return len(self.taskThreads)

    def addTaskExtraCallback(self, taskId: int, callbackFunc: Callable[[], None], args: Any = None) -> None:
        if taskId is None: # add for all tasks
            for taskId in self.taskNotifiers:
                taskFuncs = self.taskNotifiers[taskId]
                if isinstance(taskFuncs, list):
                    taskFuncs.append((callbackFunc, args))
                else:
                    self.taskNotifiers[taskId] = [taskFuncs, (callbackFunc, args)]
        else:
            taskFuncs = self.taskNotifiers[taskId]
            if isinstance(taskFuncs, list):
                taskFuncs.append((callbackFunc, args))
            else:
                self.taskNotifiers[taskId] = [taskFuncs, (callbackFunc, args)]

    def _threadSlot(self, atuple: Tuple[int, int, Any]) -> None:
        taskId, msgId, args = atuple
        sysThreadId = current_thread_id()
        if self.debugPrint:
            logfunc('slot runs in thread id {}, signal emitted from taskId {}, msgId {}[{}]'.format(
                sysThreadId, taskId, msgId, self.msgIdName.get(msgId, '?')))
        if isinstance(self.taskNotifiers[taskId], list):
            self.taskNotifiers[taskId][0](taskId, msgId, args)
            for func, argv in self.taskNotifiers[taskId][1:]:  # [1:] are callbacks added by addExtraCallback
                if self.debugPrint:
                    logfunc('----call extra callback----')
                func(argv)
        else:
            self.taskNotifiers[taskId](taskId, msgId, args)
        if msgId == MsgIDThreadExit:
            thread = self.taskThreads.get(taskId)
            if thread is not None:
                thread.wait(_WAIT_FOREVER_MS)
            del self.taskThreads[taskId]
            del self.taskNotifiers[taskId]
