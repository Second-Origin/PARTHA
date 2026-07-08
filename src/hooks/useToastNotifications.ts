import { useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { useAppStore } from '@/store/useAppStore';

export function useToastNotifications() {
  const notifications = useAppStore((s) => s.notifications);
  const lastCount = useRef(0);

  useEffect(() => {
    if (notifications.length > lastCount.current) {
      const latest = notifications[0];
      if (latest) {
        switch (latest.type) {
          case 'success':
            toast.success(latest.title, { description: latest.message });
            break;
          case 'error':
            toast.error(latest.title, { description: latest.message });
            break;
          case 'warning':
            toast.warning(latest.title, { description: latest.message });
            break;
          default:
            toast.info(latest.title, { description: latest.message });
        }
      }
    }
    lastCount.current = notifications.length;
  }, [notifications]);
}
